# python Questionnaire_SVI/dataprocess/prepare_from_findtop20.py --input_csv 4_FindTop20/outputs/M2_m5_skyscraper/m2_m5_skyscraper_top20_review_sheet.csv --query_id M2 --activate

"""
Prepare Questionnaire_SVI web inputs from a 4_FindTop20 review sheet.

This adapter keeps all method/rank metadata from the review sheet, copies images
into Questionnaire_SVI/web/images, and writes an annotation_items CSV that can be
used directly by Questionnaire_SVI/web/app.py.
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve()
QUESTIONNAIRE_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = QUESTIONNAIRE_ROOT.parent
WEB_DIR = QUESTIONNAIRE_ROOT / "web"
DEFAULT_QUERIES_CSV = WEB_DIR / "queries.csv"
DEFAULT_OUTPUT_CSV = WEB_DIR / "annotation_items.csv"
DEFAULT_IMAGES_DIR = WEB_DIR / "images"


def safe_filename(value: str, max_len: int = 120) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(value).strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    return (cleaned or "item")[:max_len]


def resolve_path(path_text: str | Path) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def write_csv(path: Path, rows: list[dict[str, str]], preferred_cols: list[str]) -> None:
    fieldnames = list(preferred_cols)
    for row in rows:
        for col in row.keys():
            if col not in fieldnames:
                fieldnames.append(col)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_query_row(queries_csv: Path, query_id: str) -> dict[str, str]:
    rows, _ = read_csv(queries_csv)
    for row in rows:
        if row.get("query_id", "").strip().lower() == query_id.strip().lower():
            return row
    raise ValueError(f"query_id={query_id} not found in {queries_csv}")


def choose_source_image(row: dict[str, str]) -> Path | None:
    for col in ["copied_image_path", "image_path"]:
        value = row.get(col, "").strip()
        if value:
            path = Path(value)
            if path.exists():
                return path
    return None


def copy_image(src: Path, dst_dir: Path, review_id: str) -> tuple[str, str]:
    dst_dir.mkdir(parents=True, exist_ok=True)
    suffix = src.suffix or ".jpg"
    image_file_name = f"{safe_filename(review_id)}{suffix}"
    dst = dst_dir / image_file_name
    shutil.copy2(src, dst)
    return image_file_name, f"images/{image_file_name}"


def build_annotation_items(
    input_rows: list[dict[str, str]],
    input_fieldnames: list[str],
    query_row: dict[str, str],
    images_dir: Path,
    seed: int,
) -> list[dict[str, str]]:
    random.seed(seed)
    display_orders = list(range(1, len(input_rows) + 1))
    random.shuffle(display_orders)

    out_rows: list[dict[str, str]] = []
    for idx, row in enumerate(input_rows):
        review_id = row.get("review_id", f"{query_row['query_id']}_{idx + 1:04d}")
        src = choose_source_image(row)
        image_file_name = ""
        web_path = ""
        copy_status = "missing"
        if src is not None:
            image_file_name, web_path = copy_image(src, images_dir, review_id)
            copy_status = "copied"

        out = dict(row)
        out["record_id"] = review_id
        out["query_id"] = query_row["query_id"]
        out["query_text"] = query_row["query_text"]
        out["query_type"] = query_row.get("query_type", "")
        out["physical_target_text"] = query_row.get("physical_target_text", "")
        out["affective_target_text"] = query_row.get("affective_target_text", "")
        out["display_order"] = str(display_orders[idx])
        out["image_file_name"] = image_file_name
        out["web_path"] = web_path
        out["copy_status"] = copy_status

        if not out.get("best_yaw") and out.get("yaw"):
            out["best_yaw"] = out["yaw"]
        if not out.get("best_view_path") and out.get("image_path"):
            out["best_view_path"] = out["image_path"]

        out_rows.append(out)

    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Questionnaire_SVI annotation_items.csv from FindTop20 review sheet.")
    parser.add_argument("--input_csv", required=True, help="4_FindTop20 review sheet CSV.")
    parser.add_argument("--query_id", required=True, help="Query ID to load from web/queries.csv.")
    parser.add_argument("--queries_csv", default=str(DEFAULT_QUERIES_CSV))
    parser.add_argument("--output_csv", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--images_dir", default=str(DEFAULT_IMAGES_DIR))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--activate", action="store_true", help="Write to web/annotation_items.csv. Kept for explicitness.")
    args = parser.parse_args()

    input_csv = resolve_path(args.input_csv)
    queries_csv = resolve_path(args.queries_csv)
    output_csv = resolve_path(args.output_csv)
    images_dir = resolve_path(args.images_dir)

    input_rows, input_fieldnames = read_csv(input_csv)
    query_row = load_query_row(queries_csv, args.query_id)
    out_rows = build_annotation_items(input_rows, input_fieldnames, query_row, images_dir, args.seed)

    preferred_cols = [
        "record_id",
        "query_id",
        "query_text",
        "query_type",
        "physical_target_text",
        "affective_target_text",
        "display_order",
        "pano_id",
        "best_yaw",
        "image_path",
        "image_file_name",
        "web_path",
        "copy_status",
    ]
    write_csv(output_csv, out_rows, preferred_cols)

    copied = sum(1 for row in out_rows if row.get("copy_status") == "copied")
    print(f"[DONE] Saved annotation items: {output_csv}")
    print(f"[DONE] Images dir: {images_dir}")
    print(f"[INFO] Rows: {len(out_rows)}")
    print(f"[INFO] Copied images: {copied}/{len(out_rows)}")


if __name__ == "__main__":
    main()
