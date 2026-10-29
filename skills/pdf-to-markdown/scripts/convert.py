#!/usr/bin/env python3
"""Convert a PDF to Markdown with pdf-inspector OCR.

Writes progressively and resumes automatically: run the same command again
after an interruption and it continues from the last completed page.

Examples:
    python convert.py book.pdf out/book.md
    python convert.py book.pdf out/book.md --pages 1-50 --dpi 200
    python convert.py book.pdf out/book.md --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from _runtime import load_pdf_inspector

PROGRESS_VERSION = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def progress_path(out: Path) -> Path:
    return out.with_name(out.name + ".progress.json")


def read_progress(out: Path, pdf: Path, total: int) -> dict | None:
    path = progress_path(out)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("version") != PROGRESS_VERSION:
        return None
    if data.get("source_size") != pdf.stat().st_size:
        return None
    if data.get("total_pages") != total:
        return None
    return data


def write_progress(out: Path, payload: dict) -> None:
    path = progress_path(out)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def append_text(out: Path, text: str) -> None:
    if not text:
        return
    with out.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())


def parse_pages(spec: str | None) -> tuple[int | None, int | None]:
    """Parse 'N' or 'N-M' into (start, end)."""
    if not spec:
        return None, None
    spec = spec.strip()
    if "-" in spec:
        begin, end = spec.split("-", 1)
        return int(begin), int(end)
    return int(spec), int(spec)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to Markdown with pdf-inspector OCR.",
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--pages", help="page range, e.g. 1-50 or 120")
    parser.add_argument("--start", type=int, help="first page (1-indexed), implies append")
    parser.add_argument("--end", type=int, help="last page (1-indexed, inclusive)")
    parser.add_argument("--batch", type=int, default=10, help="pages per OCR call")
    parser.add_argument("--dpi", type=float, default=150.0)
    parser.add_argument(
        "--mode",
        choices=("force", "auto"),
        default="force",
        help="force OCR every page, or let the engine route pages",
    )
    parser.add_argument("--overwrite", action="store_true", help="discard output and restart")
    parser.add_argument("--quiet", action="store_true", help="print only errors")
    args = parser.parse_args()

    pdf = args.pdf.expanduser().resolve()
    if not pdf.is_file():
        print(f"error: PDF not found: {pdf}", file=sys.stderr)
        return 2
    if args.batch < 1:
        print("error: --batch must be >= 1", file=sys.stderr)
        return 2

    inspector = load_pdf_inspector()
    cls = inspector.classify_pdf(str(pdf))
    total = int(getattr(cls, "page_count", 0) or 0)
    if total < 1:
        print(f"error: could not read page count for {pdf}", file=sys.stderr)
        return 2

    out = args.out.expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    range_start, range_end = parse_pages(args.pages)
    if args.start is not None:
        range_start = args.start
    if args.end is not None:
        range_end = args.end
    start = max(1, range_start or 1)
    end = min(total, range_end or total)
    if start > end:
        print(f"error: empty page range {start}-{end}", file=sys.stderr)
        return 2

    if args.overwrite:
        for path in (out, progress_path(out)):
            if path.exists():
                path.unlink()
        start = max(1, range_start or 1)

    progress = read_progress(out, pdf, total)
    resumed = False
    if progress and not args.overwrite:
        if progress.get("done") and progress.get("last_page", 0) >= end:
            print(
                f"already complete: {out} ({progress.get('last_page')} pages). "
                "Use --overwrite to redo.",
                file=sys.stderr,
            )
            return 0
        last_page = int(progress.get("last_page", 0))
        if start <= last_page < end:
            start = last_page + 1
            resumed = True

    if not resumed and out.exists() and out.stat().st_size > 0 and not args.overwrite:
        print(
            f"error: {out} already exists. Use --overwrite to restart, or "
            "--start N to append from page N.",
            file=sys.stderr,
        )
        return 2

    if not args.quiet:
        print(
            f"source  {pdf.name}  type={getattr(cls, 'pdf_type', '?')}  pages={total}",
            flush=True,
        )
        print(
            f"output  {out}  pages={start}-{end}  dpi={args.dpi:g}  mode={args.mode}  "
            f"batch={args.batch}{'  (resume)' if resumed else ''}",
            flush=True,
        )

    if resumed:
        tail = b""
        if out.exists() and out.stat().st_size >= 2:
            with out.open("rb") as fh:
                fh.seek(-2, os.SEEK_END)
                tail = fh.read(2)
        if tail == b"\n\n":
            pass
        elif tail.endswith(b"\n"):
            append_text(out, "\n")
        else:
            append_text(out, "\n\n")

    state = {
        "version": PROGRESS_VERSION,
        "source": str(pdf),
        "source_size": pdf.stat().st_size,
        "total_pages": total,
        "last_page": start - 1,
        "dpi": args.dpi,
        "mode": args.mode,
        "batch": args.batch,
        "done": False,
        "started_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_progress(out, state)

    session_started = time.perf_counter()
    pages_this_run = 0
    chars_this_run = 0

    try:
        for begin in range(start, end + 1, args.batch):
            batch_end = min(begin + args.batch - 1, end)
            pages = list(range(begin, batch_end + 1))
            batch_started = time.perf_counter()
            result = inspector.process_pdf_with_ocr(
                str(pdf), mode=args.mode, page_numbers=pages, dpi=args.dpi
            )
            batch_wall = time.perf_counter() - batch_started
            text = (result.markdown or "").strip()
            if text:
                append_text(out, text + "\n\n")
            chars_this_run += len(text)
            pages_this_run += len(pages)

            state["last_page"] = batch_end
            state["updated_at"] = now_iso()
            write_progress(out, state)

            if not args.quiet:
                elapsed = time.perf_counter() - session_started
                rate = pages_this_run / elapsed if elapsed > 0 else 0.0
                remaining = (end - batch_end) / rate if rate > 0 else 0.0
                print(
                    f"pages {begin}-{batch_end}/{end}  "
                    f"batch={batch_wall:.1f}s  chars=+{len(text):,}  "
                    f"elapsed={elapsed / 60:.1f}m  eta={remaining / 60:.1f}m",
                    flush=True,
                )
    except KeyboardInterrupt:
        write_progress(out, state)
        written = out.stat().st_size if out.exists() else 0
        print(
            f"\ninterrupted at page {state['last_page']}/{end}; "
            f"{written:,} bytes kept. Re-run the same command to resume.",
            file=sys.stderr,
        )
        return 130
    except Exception as exc:  # noqa: BLE001 - report and keep resumable state
        write_progress(out, state)
        print(
            f"\nerror at page {state['last_page'] + 1}/{end}: {exc}\n"
            "Progress saved. Fix the cause and re-run the same command to resume.",
            file=sys.stderr,
        )
        return 1

    state["done"] = True
    state["updated_at"] = now_iso()
    write_progress(out, state)

    elapsed = time.perf_counter() - session_started
    size = out.stat().st_size if out.exists() else 0
    print(
        f"done: {out}  pages={start}-{end}  chars=+{chars_this_run:,}  "
        f"bytes={size:,}  elapsed={elapsed / 60:.1f}m",
        file=sys.stderr if args.quiet else sys.stdout,
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
