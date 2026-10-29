"""Shared runtime discovery for pdf-to-markdown scripts.

Both probe.py and convert.py use this so the OCR runtime is located the same
way. Resolution order for each native library:

1. the explicit environment variable (PDFIUM_LIB_PATH / ORT_DYLIB_PATH)
2. a matching library file under $OCR_HOME (default ~/.ocr-runtime)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

LIB_NAMES = {
    "pdfium": ("pdfium.dll", "libpdfium.so", "libpdfium.dylib", "pdfium"),
    "ort": (
        "onnxruntime.dll",
        "libonnxruntime.so",
        "libonnxruntime.dylib",
        "onnxruntime",
    ),
}

INSTALL_HINT = """\
pdf_inspector is not installed. Install it with:

    pip install pdf-inspector

Or use anydoc for PDFs that already contain a text layer:

    npm install -g @firecrawl/anydoc
"""


def runtime_home() -> Path:
    """Root directory holding the shared OCR libraries and models."""
    override = os.environ.get("OCR_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".ocr-runtime"


def find_library(root: Path, names: tuple[str, ...]) -> Path | None:
    if not root.exists():
        return None
    for name in names:
        direct = root / name
        if direct.is_file():
            return direct
        for hit in root.rglob(name):
            if hit.is_file():
                return hit
    return None


def setup_env() -> dict[str, str]:
    """Populate PDFIUM_LIB_PATH / ORT_DYLIB_PATH when they are unset.

    Returns a mapping of every variable that is set, whether by the caller or
    by this function, so callers can print a useful diagnostic.
    """
    home = runtime_home()
    resolved: dict[str, str] = {}
    for env_key, subdir, names in (
        ("PDFIUM_LIB_PATH", "pdfium", LIB_NAMES["pdfium"]),
        ("ORT_DYLIB_PATH", "ort", LIB_NAMES["ort"]),
    ):
        current = os.environ.get(env_key)
        if current:
            resolved[env_key] = current
            continue
        found = find_library(home / subdir, names)
        if found is not None:
            os.environ[env_key] = str(found)
            resolved[env_key] = str(found)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    return resolved


def load_pdf_inspector():
    setup_env()
    try:
        import pdf_inspector  # noqa: PLC0415 - deferred so --check can report cleanly
    except ImportError as exc:
        raise SystemExit(INSTALL_HINT) from exc
    return pdf_inspector


def describe_environment() -> list[str]:
    import sys

    lines = [f"python: {sys.version.split()[0]}"]
    home = runtime_home()
    lines.append(f"OCR_HOME: {home} ({'exists' if home.exists() else 'missing'})")

    for env_key, subdir, names in (
        ("PDFIUM_LIB_PATH", "pdfium", LIB_NAMES["pdfium"]),
        ("ORT_DYLIB_PATH", "ort", LIB_NAMES["ort"]),
    ):
        value = os.environ.get(env_key)
        if value:
            state = "ok" if Path(value).is_file() else "FILE NOT FOUND"
            lines.append(f"{env_key}: {value} ({state})")
        else:
            fallback = find_library(home / subdir, names)
            if fallback:
                lines.append(f"{env_key}: unset, found at {fallback}")
            else:
                lines.append(f"{env_key}: unset, not found under {home / subdir}")

    try:
        import pdf_inspector

        version = getattr(pdf_inspector, "__version__", "unknown")
        lines.append(f"pdf_inspector: ok (version {version})")
    except ImportError:
        lines.append("pdf_inspector: not installed")

    anydoc = shutil.which("anydoc")
    lines.append(f"anydoc: {anydoc or 'not found'}")
    if not home.exists():
        lines.append(
            "hint: set OCR_HOME to an existing runtime directory, or download "
            "PDFium + ONNX Runtime into " + str(home)
        )
    return lines
