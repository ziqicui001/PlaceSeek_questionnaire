"""
Append one ranked CSV as a task in the questionnaire app.

This is useful for ablation outputs that are already ranked but are not stored
as a 4_FindTop20 review sheet or Final_Ranking_Tables folder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from prepare_from_findtop20 import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_QUERIES_CSV,
    build_annotation_items,
    load_query_row,
    read_csv,
    resolve_path,
    write_csv,
)


def clean_text(value: str | None) -> str:
    return str(value or "").strip()


def rank_value(row: dict[str, str], rank_col: str) -> tuple[int, float | str]:
    text = clean_text(row.get(rank_col))
    if not text:
        return 1, ""
    try:
        return 0, float(text)
    except ValueError:
        return 0, text


def next_display_start(rows: list[dict[str, str]]) -> int:
    max_order = 0
    for row in rows:
        try:
            max_order = max(max_order, int(float(clean_text(row.get("display_order")) or "0")))
        except ValueError:
            continue
    return max_order + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a ranked CSV as one questionnaire task.")
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--query_id", required=True)
    parser.add_argument("--rank_col", default="final_rank")
    parser.add_argument("--top_k", type=int, default=20)
    parser.add_argument("--base_items_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--output_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--queries_csv", default=str(DEFAULT_QUERIES_CSV))
    parser.add_argument("--images_dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--replace_task",
        action="store_true",
        help="Remove existing rows with this query_id before appending the new task.",
    )
    parser.add_argument("--activate", action="store_true", help="Write to web/annotation_items.csv. Kept for explicitness.")
    args = parser.parse_args()

    input_csv = resolve_path(args.input_csv)
    base_items_csv = resolve_path(args.base_items_csv)
    output_csv = resolve_path(args.output_csv)
    queries_csv = resolve_path(args.queries_csv)
    images_dir = resolve_path(args.images_dir)

    base_rows, _ = read_csv(base_items_csv)
    if args.replace_task:
        base_rows = [row for row in base_rows if clean_text(row.get("query_id")).upper() != args.query_id.upper()]
    elif any(clean_text(row.get("query_id")).upper() == args.query_id.upper() for row in base_rows):
        raise ValueError(f"Task already exists: {args.query_id}. Use --replace_task to regenerate it.")

    input_rows, input_fieldnames = read_csv(input_csv)
    if args.rank_col not in input_fieldnames:
        raise ValueError(f"Rank column not found in input CSV: {args.rank_col}")

    ranked_rows = sorted(input_rows, key=lambda row: rank_value(row, args.rank_col))[: args.top_k]
    query_row = load_query_row(queries_csv, args.query_id)
    prepared_rows = build_annotation_items(
        input_rows=ranked_rows,
        input_fieldnames=input_fieldnames,
        query_row=query_row,
        images_dir=images_dir,
        seed=args.seed,
    )

    display_start = next_display_start(base_rows)
    for offset, row in enumerate(prepared_rows):
        row["display_order"] = str(display_start + offset)
        row["source_task_type"] = "ranked_task"
        row["source_ranked_csv"] = str(input_csv)
        row["source_rank_col"] = args.rank_col
        row["source_top_k"] = str(args.top_k)

    all_rows = base_rows + prepared_rows
    preferred_cols = [
        "record_id",
        "query_id",
        "source_query_id",
        "source_task_type",
        "query_text",
        "query_type",
        "physical_target_text",
        "affective_target_text",
        "instruction_text",
        "display_order",
        "pano_id",
        "best_yaw",
        "yaw",
        "lng",
        "lat",
        "image_path",
        "best_view_path",
        "image_file_name",
        "web_path",
        "copy_status",
        "source_ranked_csv",
        "source_rank_col",
        "source_top_k",
    ]
    write_csv(output_csv, all_rows, preferred_cols)

    copied = sum(1 for row in prepared_rows if row.get("copy_status") == "copied")
    print(f"[DONE] Saved annotation items: {output_csv}")
    print(f"[INFO] Existing rows kept: {len(base_rows)}")
    print(f"[INFO] Added task: {args.query_id}")
    print(f"[INFO] Added rows: {len(prepared_rows)}")
    print(f"[INFO] Copied images: {copied}/{len(prepared_rows)}")


if __name__ == "__main__":
    main()
