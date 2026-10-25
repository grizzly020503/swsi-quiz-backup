#!/usr/bin/env python3
"""Stage exact MOEX chart images from the original 120-PDF evidence archive.

Does not modify official questions, grades, production, UI, or release approval.
Use: python scripts/extract_official_figure_assets.py --archive ORIGINAL.zip --output-dir /tmp/swsi-figures
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ARCHIVE_SHA256 = "6e1258de9890efc85714a3e4b0fefcdbd552cae3dd5f6c5dc14735f068de428f"
PDF_FIGURES = (
    {
        "id": "DS-113-2-13",
        "pdf": "113100-103-0302.pdf",
        "pdf_sha256": "21b47d133e072b34eab4f07fa95ffab1601d54768eb8cedf680a9471fc9bfbc3",
        "page_index": 2,
        "printed_page": "6-3",
        "clip": (69.12, 100.07, 429.84, 418.08),
        "png_sha256": "ead831603f8da4617dc1b3d0cb077e1ce5f3cdaebfe6a3670f4cf0ec852e5c15",
    },
    {
        "id": "R-114-2-12",
        "pdf": "114100-103-0306.pdf",
        "pdf_sha256": "f0da4551b15af06b68d0ff3a287acb2b0253ddecef7e6fdd76e768e8ca990ae2",
        "page_index": 1,
        "printed_page": "4-2",
        "clip": (191.04, 457.44, 427.92, 528.0),
        "png_sha256": "3ee93de068499079f7630f71ab39bba12369bd56f0ad3c05a464fde1a7f4a90e",
    },
)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def extract(archive: Path, output: Path):
    raw = archive.read_bytes()
    if digest(raw) != ARCHIVE_SHA256:
        raise ValueError("Original 120-PDF evidence archive checksum mismatch")
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Requires PyMuPDF==1.26.7") from exc
    if fitz.VersionBind != "1.26.7":
        raise RuntimeError("Exact evidence rendering requires PyMuPDF==1.26.7")
    images = []
    with zipfile.ZipFile(archive) as z:
        for record in PDF_FIGURES:
            pdf = z.read(record["pdf"])
            if digest(pdf) != record["pdf_sha256"]:
                raise ValueError("Original official PDF hash mismatch: " + record["pdf"])
            doc = fitz.open(stream=pdf, filetype="pdf")
            if len(doc) <= record["page_index"]:
                raise ValueError("Missing official page: " + record["pdf"])
            png = doc[record["page_index"]].get_pixmap(
                matrix=fitz.Matrix(2.7, 2.7),
                clip=fitz.Rect(*record["clip"]),
                alpha=False,
            ).tobytes("png")
            if digest(png) != record["png_sha256"]:
                raise ValueError("Official chart raster differs from visually verified evidence: " + record["id"])
            images.append((record, png))
    # Fail before writing anything if either verified image differs.
    output.mkdir(parents=True, exist_ok=True)
    for record, png in images:
        (output / (record["id"] + ".png")).write_bytes(png)
    manifest = {
        "schema_version": 1,
        "source_archive_sha256": ARCHIVE_SHA256,
        "status": "EVIDENCE_ONLY_HUMAN_REVIEW_REQUIRED",
        "official_core_modified": False,
        "production_modified": False,
        "release_approved": False,
        "figures": [
            {
                "id": item["id"],
                "pdf": item["pdf"],
                "pdf_sha256": item["pdf_sha256"],
                "page": item["printed_page"],
                "clip_pdf_points": list(item["clip"]),
                "png_filename": item["id"] + ".png",
                "png_sha256": item["png_sha256"],
            }
            for item, _ in images
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        m = extract(args.archive, args.output_dir)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as e:
        print("OFFICIAL FIGURE EXTRACTION BLOCKED: " + str(e), file=sys.stderr)
        return 2
    print("OFFICIAL FIGURE EVIDENCE READY: " + str(len(m["figures"])) + " sources; release remains NO-GO")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
