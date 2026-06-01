"""
Append supplement annotation tasks from Final_Ranking_Tables.

This script keeps the existing deployed questionnaire items, then adds only new
image/query pairs from 3_Rerank/Rerank_final/Final_Ranking_Tables. Existing
query tasks are added as QUERY_supplement, while completely new queries keep
their original task ID.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from prepare_from_findtop20 import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_QUERIES_CSV,
    REPO_ROOT,
    WEB_DIR,
    build_annotation_items,
    load_query_row,
    read_csv,
    resolve_path,
    write_csv,
)


DEFAULT_FINAL_ROOT = REPO_ROOT / "3_Rerank" / "Rerank_final" / "Final_Ranking_Tables"
DEFAULT_SUMMARY_CSV = WEB_DIR / "annotation_items_supplement_summary.csv"


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
    query_id = clean_text(
        row.get("source_query_id")
        or row.get("original_query_id")
        or row.get("query_id")
    )
    if query_id.lower().endswith("_supplement"):
        return query_id[: -len("_supplement")]
    return query_id


def dedupe_key(row: dict[str, str], fallback_query_id: str = "") -> tuple[str, str]:
    query_id = source_query_id(row) or fallback_query_id
    explicit_key = clean_text(row.get("dedupe_key")).lower()
    if explicit_key:
        return query_id.upper(), explicit_key

    pano_id = clean_text(row.get("pano_id")).lower()
    yaw = normalize_yaw(row.get("yaw") or row.get("best_yaw") or "")
    return query_id.upper(), f"{pano_id}::{yaw}"


def discover_query_csvs(final_root: Path, selected_queries: list[str] | None) -> list[tuple[str, Path]]:
    if selected_queries:
        query_ids = selected_queries
    else:
        query_ids = sorted(path.name for path in final_root.iterdir() if path.is_dir())

    jobs = []
    for query_id in query_ids:
        csv_path = final_root / query_id / f"{query_id.lower()}_m5_final_ranking_top20.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Final ranking table not found for {query_id}: {csv_path}")
        jobs.append((query_id, csv_path))
    return jobs


def next_display_start(rows: list[dict[str, str]]) -> int:
    max_order = 0
    for row in rows:
        try:
            max_order = max(max_order, int(float(clean_text(row.get("display_order")) or "0")))
        except ValueError:
            continue
    return max_order + 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Append non-duplicated Final_Ranking_Tables rows as questionnaire supplement tasks."
    )
    parser.add_argument("--final_root", default=str(DEFAULT_FINAL_ROOT))
    parser.add_argument("--base_items_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--queries_csv", default=str(DEFAULT_QUERIES_CSV))
    parser.add_argument("--output_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--images_dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--summary_csv", default=str(DEFAULT_SUMMARY_CSV))
    parser.add_argument(
        "--query",
        action="append",
        help="Limit to one query ID. Repeat for multiple queries. Defaults to every query directory in final_root.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Write to web/annotation_items.csv. Kept for explicitness.",
    )
    args = parser.parse_args()

    final_root = resolve_path(args.final_root)
    base_items_csv = resolve_path(args.base_items_csv)
    queries_csv = resolve_path(args.queries_csv)
    output_csv = resolve_path(args.output_csv)
    images_dir = resolve_path(args.images_dir)
    summary_csv = resolve_path(args.summary_csv)

    base_rows, _ = read_csv(base_items_csv)
    existing_keys = {dedupe_key(row) for row in base_rows}
    existing_query_ids = {clean_text(row.get("query_id")).upper() for row in base_rows}

    all_rows = list(base_rows)
    summary_rows = []
    display_start = next_display_start(all_rows)

    for query_id, input_csv in discover_query_csvs(final_root, args.query):
        input_rows, input_fieldnames = read_csv(input_csv)
        new_rows = []
        seen_new_keys = set()
        for row in input_rows:
            key = dedupe_key(row, query_id)
            if key in existing_keys or key in seen_new_keys:
                continue
            seen_new_keys.add(key)
            new_rows.append(row)

        if not new_rows:
            summary_rows.append(
                {
                    "query_id": query_id,
                    "task_query_id": "",
                    "input_csv": str(input_csv),
                    "input_rows": str(len(input_rows)),
                    "new_rows": "0",
                    "copied_images": "0",
                    "status": "skipped_no_new_images",
                }
            )
            continue

        task_query_id = query_id if query_id.upper() not in existing_query_ids else f"{query_id}_supplement"
        query_row = load_query_row(queries_csv, query_id)
        query_row["query_id"] = task_query_id

        prepared_rows = build_annotation_items(
            input_rows=new_rows,
            input_fieldnames=input_fieldnames,
            query_row=query_row,
            images_dir=images_dir,
            seed=args.seed,
        )

        for offset, row in enumerate(prepared_rows):
            row["display_order"] = str(display_start + offset)
            row["source_query_id"] = query_id
            row["source_task_type"] = "new_task" if task_query_id == query_id else "supplement"
            row["source_final_csv"] = str(input_csv)
        display_start += len(prepared_rows)

        all_rows.extend(prepared_rows)
        existing_keys.update(dedupe_key(row, query_id) for row in new_rows)
        existing_query_ids.add(task_query_id.upper())

        copied = sum(1 for row in prepared_rows if row.get("copy_status") == "copied")
        summary_rows.append(
            {
                "query_id": query_id,
                "task_query_id": task_query_id,
                "input_csv": str(input_csv),
                "input_rows": str(len(input_rows)),
                "new_rows": str(len(prepared_rows)),
                "copied_images": str(copied),
                "status": "added",
            }
        )

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
        "image_file_name",
        "web_path",
        "copy_status",
        "source_final_csv",
    ]
    write_csv(output_csv, all_rows, preferred_cols)
    write_csv(
        summary_csv,
        summary_rows,
        ["query_id", "task_query_id", "input_csv", "input_rows", "new_rows", "copied_images", "status"],
    )

    added = sum(int(row["new_rows"]) for row in summary_rows)
    copied_total = sum(int(row["copied_images"]) for row in summary_rows)
    print(f"[DONE] Saved annotation items: {output_csv}")
    print(f"[DONE] Saved supplement summary: {summary_csv}")
    print(f"[INFO] Existing rows kept: {len(base_rows)}")
    print(f"[INFO] Supplement rows added: {added}")
    print(f"[INFO] Supplement images copied: {copied_total}/{added}")


if __name__ == "__main__":
    main()
