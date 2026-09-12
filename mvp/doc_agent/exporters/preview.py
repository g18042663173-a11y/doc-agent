from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from doc_agent.config import get_settings


def export_pages_to_images(
    input_path: str | Path,
    out_dir: str | Path,
    soffice_path: str | None = None,
    pdftoppm_path: str | None = None,
) -> list[Path]:
    settings = get_settings()
    source = Path(input_path)
    output_dir = Path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    soffice = _resolve_tool(soffice_path or settings.soffice_path, "soffice", "LibreOffice")
    pdftoppm = _resolve_tool(pdftoppm_path or settings.pdftoppm_path, "pdftoppm", "Poppler")

    subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    pdf_path = output_dir / f"{source.stem}.pdf"
    if not pdf_path.exists():
        candidates = sorted(output_dir.glob("*.pdf"))
        if len(candidates) == 1:
            pdf_path = candidates[0]
        else:
            raise RuntimeError("LibreOffice conversion finished but no PDF was produced.")

    prefix = output_dir / source.stem
    subprocess.run(
        [pdftoppm, "-png", str(pdf_path), str(prefix)],
        check=True,
        capture_output=True,
        text=True,
    )
    images = sorted(output_dir.glob(f"{source.stem}-*.png"))
    if not images:
        raise RuntimeError("pdftoppm conversion finished but no PNG pages were produced.")
    return images


def _resolve_tool(configured: str | None, binary: str, label: str) -> str:
    if configured:
        path = Path(configured)
        if path.exists():
            return str(path)
        resolved_configured = shutil.which(configured)
        if resolved_configured:
            return resolved_configured
    resolved = shutil.which(binary)
    if resolved:
        return resolved
    raise RuntimeError(f"{label} command '{binary}' was not found. Install it or set the matching *_PATH environment variable.")
