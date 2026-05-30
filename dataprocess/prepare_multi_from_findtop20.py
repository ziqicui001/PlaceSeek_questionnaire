# python PlaceSeek_questionnaire/dataprocess/prepare_multi_from_findtop20.py --job A3=4_FindTop20/outputs_physical_affective/A3_m5_physical_affective/a3_m5_physical_affective_top20_review_sheet.csv --job A4=4_FindTop20/outputs_physical_affective/A4_m5_physical_affective/a4_m5_physical_affective_top20_review_sheet.csv --clear_images --activate

"""
Prepare a multi-query Questionnaire_SVI web dataset from multiple FindTop20 sheets.

Use this when one online questionnaire should contain several query tasks. Each
row keeps its own query_id, query_text, physical requirement, and affective
requirement, so the Streamlit app can display task-specific instructions.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from prepare_from_findtop20 import (
    DEFAULT_IMAGES_DIR,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_QUERIES_CSV,
    build_annotation_items,
    clear_image_dir,
    load_query_row,
    read_csv,
    resolve_path,
    write_csv,
)


def parse_job(job_text: str) -> tuple[str, Path]:
    if "=" not in job_text:
        raise ValueError(f"Job must be formatted as QUERY_ID=CSV_PATH, got: {job_text}")
    query_id, csv_path = job_text.split("=", 1)
    query_id = query_id.strip()
    csv_path = csv_path.strip().strip('"')
    if not query_id or not csv_path:
        raise ValueError(f"Invalid job: {job_text}")
    return query_id, resolve_path(csv_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare one questionnaire from multiple FindTop20 review sheets.")
    parser.add_argument(
        "--job",
        action="append",
        required=True,
        help="One query job as QUERY_ID=CSV_PATH. Repeat for multiple queries.",
    )
    parser.add_argument("--queries_csv", default=str(DEFAULT_QUERIES_CSV))
    parser.add_argument("--output_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--images_dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--clear_images", action="store_true", help="Delete existing images before copying.")
    parser.add_argument("--activate", action="store_true", help="Write to web/annotation_items.csv. Kept for explicitness.")
    args = parser.parse_args()

    queries_csv = resolve_path(args.queries_csv)
    output_csv = resolve_path(args.output_csv)
    images_dir = resolve_path(args.images_dir)

    removed = clear_image_dir(images_dir) if args.clear_images else 0

    all_rows = []
    summary_rows = []
    for job_text in args.job:
        query_id, input_csv = parse_job(job_text)
        input_rows, input_fieldnames = read_csv(input_csv)
        query_row = load_query_row(queries_csv, query_id)
        prepared_rows = build_annotation_items(
            input_rows=input_rows,
            input_fieldnames=input_fieldnames,
            query_row=query_row,
            images_dir=images_dir,
            seed=args.seed,
        )
        all_rows.extend(prepared_rows)
        copied = sum(1 for row in prepared_rows if row.get("copy_status") == "copied")
        summary_rows.append(
            {
                "query_id": query_id,
                "input_csv": str(input_csv),
                "rows": str(len(prepared_rows)),
                "copied_images": str(copied),
                "query_text": query_row.get("query_text", ""),
            }
        )

    random.seed(args.seed)
    display_orders = list(range(1, len(all_rows) + 1))
    random.shuffle(display_orders)
    for idx, row in enumerate(all_rows):
        row["display_order"] = str(display_orders[idx])

    preferred_cols = [
        "record_id",
        "query_id",
        "query_text",
        "query_type",
        "physical_target_text",
        "affective_target_text",
        "instruction_text",
        "display_order",
        "pano_id",
        "best_yaw",
        "image_path",
        "image_file_name",
        "web_path",
        "copy_status",
    ]
    write_csv(output_csv, all_rows, preferred_cols)

    summary_csv = output_csv.with_name(output_csv.stem + "_multi_summary.csv")
    write_csv(summary_csv, summary_rows, ["query_id", "rows", "copied_images", "input_csv", "query_text"])

    copied_total = sum(1 for row in all_rows if row.get("copy_status") == "copied")
    print(f"[DONE] Saved annotation items: {output_csv}")
    print(f"[DONE] Saved summary: {summary_csv}")
    print(f"[DONE] Images dir: {images_dir}")
    if args.clear_images:
        print(f"[INFO] Cleared old images: {removed}")
    print(f"[INFO] Total rows: {len(all_rows)}")
    print(f"[INFO] Copied images: {copied_total}/{len(all_rows)}")


if __name__ == "__main__":
    main()
