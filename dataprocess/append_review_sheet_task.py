"""
Append a FindTop20 review sheet as a supplement questionnaire task.

Rows already present for the same source query are skipped by pano_id/yaw, so
annotators do not need to re-label images that were already published.
"""

from __future__ import annotations

import argparse

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


def normalize_yaw(value: str) -> str:
    text = clean_text(value)
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text.lower()
    if number.is_integer():
        return str(int(number))
    return str(number)


def source_query_id(row: dict[str, str]) -> str:
    query_id = clean_text(row.get("source_query_id") or row.get("original_query_id") or row.get("query_id"))
    if query_id.lower().endswith("_supplement"):
        return query_id[: -len("_supplement")]
    return query_id


def image_key(row: dict[str, str], fallback_query_id: str) -> tuple[str, str]:
    query_id = source_query_id(row) or fallback_query_id
    explicit_key = clean_text(row.get("dedupe_key")).lower()
    if explicit_key:
        return query_id.upper(), explicit_key

    pano_id = clean_text(row.get("pano_id")).lower()
    yaw = normalize_yaw(row.get("yaw") or row.get("best_yaw") or "")
    return query_id.upper(), f"{pano_id}::{yaw}"


def next_display_start(rows: list[dict[str, str]]) -> int:
    max_order = 0
    for row in rows:
        try:
            max_order = max(max_order, int(float(clean_text(row.get("display_order")) or "0")))
        except ValueError:
            continue
    return max_order + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Append a de-duplicated review sheet as a questionnaire task.")
    parser.add_argument("--input_csv", required=True)
    parser.add_argument("--source_query_id", required=True, help="Original query ID used for loading prompt/terms and de-duplication.")
    parser.add_argument("--task_query_id", required=True, help="Task ID shown in the website, e.g. M4_supplement.")
    parser.add_argument("--base_items_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--output_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--queries_csv", default=str(DEFAULT_QUERIES_CSV))
    parser.add_argument("--images_dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow_existing_task", action="store_true", help="Append even if task_query_id already exists.")
    parser.add_argument("--activate", action="store_true", help="Write to web/annotation_items.csv. Kept for explicitness.")
    args = parser.parse_args()

    input_csv = resolve_path(args.input_csv)
    base_items_csv = resolve_path(args.base_items_csv)
    output_csv = resolve_path(args.output_csv)
    queries_csv = resolve_path(args.queries_csv)
    images_dir = resolve_path(args.images_dir)

    base_rows, _ = read_csv(base_items_csv)
    if not args.allow_existing_task and any(
        clean_text(row.get("query_id")).upper() == args.task_query_id.upper() for row in base_rows
    ):
        raise ValueError(f"Task already exists: {args.task_query_id}. Use --allow_existing_task to append anyway.")

    existing_keys = {image_key(row, args.source_query_id) for row in base_rows}
    input_rows, input_fieldnames = read_csv(input_csv)

    new_rows = []
    seen_new_keys = set()
    for row in input_rows:
        key = image_key(row, args.source_query_id)
        if key in existing_keys or key in seen_new_keys:
            continue
        seen_new_keys.add(key)
        out = dict(row)
        out["review_id"] = f"{args.task_query_id}_{len(new_rows) + 1:04d}"
        new_rows.append(out)

    query_row = load_query_row(queries_csv, args.source_query_id)
    query_row["query_id"] = args.task_query_id

    prepared_rows = build_annotation_items(
        input_rows=new_rows,
        input_fieldnames=input_fieldnames,
        query_row=query_row,
        images_dir=images_dir,
        seed=args.seed,
    )

    display_start = next_display_start(base_rows)
    for offset, row in enumerate(prepared_rows):
        row["display_order"] = str(display_start + offset)
        row["source_query_id"] = args.source_query_id
        row["source_task_type"] = "review_sheet_supplement"
        row["source_review_sheet_csv"] = str(input_csv)

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
        "copied_image_path",
        "image_file_name",
        "web_path",
        "copy_status",
        "source_review_sheet_csv",
    ]
    write_csv(output_csv, all_rows, preferred_cols)

    copied = sum(1 for row in prepared_rows if row.get("copy_status") == "copied")
    print(f"[DONE] Saved annotation items: {output_csv}")
    print(f"[INFO] Existing rows kept: {len(base_rows)}")
    print(f"[INFO] Input rows: {len(input_rows)}")
    print(f"[INFO] Added task: {args.task_query_id}")
    print(f"[INFO] Added rows: {len(prepared_rows)}")
    print(f"[INFO] Copied images: {copied}/{len(prepared_rows)}")


if __name__ == "__main__":
    main()
