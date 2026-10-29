#!/usr/bin/env python3
"""Classify a PDF and, optionally, benchmark OCR speed before converting it.

Examples:
    python probe.py --check
    python probe.py book.pdf
    python probe.py book.pdf --pages 20,21,22 --time
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from _runtime import describe_environment, load_pdf_inspector

SLOW_PAGE_SECONDS = 5.0


def parse_pages(spec: str, total: int) -> list[int]:
    pages: list[int] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            begin, end = chunk.split("-", 1)
            pages.extend(range(int(begin), int(end) + 1))
        else:
            pages.append(int(chunk))
    pages = sorted({p for p in pages if 1 <= p <= total})
    if not pages:
        raise ValueError(f"no page in 1..{total} matched {spec!r}")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Classify a PDF and benchmark pdf-inspector OCR.",
    )
    parser.add_argument("pdf", nargs="?", help="path to the PDF")
    parser.add_argument(
        "--check",
        action="store_true",
        help="report the OCR runtime environment and exit",
    )
    parser.add_argument(
        "--pages",
        help="pages to OCR when benchmarking, e.g. 20 or 20,21,22 or 20-25",
    )
    parser.add_argument(
        "--time",
        dest="timed",
        action="store_true",
        help="actually OCR the selected pages and measure throughput",
    )
    parser.add_argument("--dpi", type=float, default=150.0)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    if args.check:
        lines = describe_environment()
        for line in lines:
            print(line)
        return 0

    if not args.pdf:
        parser.error("PDF path is required unless --check is used")

    pdf = Path(args.pdf).expanduser()
    if not pdf.is_file():
        print(f"error: PDF not found: {pdf}", file=sys.stderr)
        return 2

    inspector = load_pdf_inspector()
    cls = inspector.classify_pdf(str(pdf))
    total = int(getattr(cls, "page_count", 0) or 0)
    pdf_type = str(getattr(cls, "pdf_type", "unknown"))
    confidence = float(getattr(cls, "confidence", 0.0) or 0.0)

    result: dict[str, object] = {
        "file": str(pdf),
        "size_bytes": pdf.stat().st_size,
        "pages": total,
        "type": pdf_type,
        "confidence": round(confidence, 3),
    }

    if args.timed:
        pages = parse_pages(args.pages, total) if args.pages else sorted(
            {p for p in (1, 2, 3) if p <= total}
        )
        started = time.perf_counter()
        batch = inspector.process_pdf_with_ocr(
            str(pdf), mode="force", page_numbers=pages, dpi=args.dpi
        )
        wall = time.perf_counter() - started
        chars = len((batch.markdown or "").strip())
        per_page = wall / max(len(pages), 1)
        result.update(
            {
                "bench_pages": pages,
                "bench_wall_s": round(wall, 2),
                "seconds_per_page": round(per_page, 2),
                "chars": chars,
                "ocr_time_ms": int(getattr(batch, "ocr_time_ms", 0) or 0),
                "estimated_total_minutes": round(per_page * total / 60, 1),
            }
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"file       {pdf}")
        print(f"pages      {total}")
        print(f"type       {pdf_type} (confidence {confidence:.2f})")
        if args.timed:
            print(f"bench      pages {result['bench_pages']} in {result['bench_wall_s']}s")
            print(f"rate       {result['seconds_per_page']} s/page")
            print(f"chars      {result['chars']}")
            print(f"estimate   {result['estimated_total_minutes']} min for {total} pages")
            if float(result["seconds_per_page"]) > SLOW_PAGE_SECONDS:
                print(
                    "warning: slower than 5 s/page; re-check the runtime before "
                    "starting a full book",
                    file=sys.stderr,
                )

    if pdf_type.lower() in {"scanned", "mixed"}:
        print(
            "hint: use convert.py (pdf-inspector OCR) rather than anydoc for this file",
            file=sys.stderr,
        )
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
