"""Build a deterministic, page-labelled PNG contact sheet from Office exports."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


MARGIN = 20
LABEL_HEIGHT = 26
BACKGROUND = "#F4F6F8"
BORDER = "#C8D0D8"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a labelled PowerPoint PNG contact sheet.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--columns", type=int, default=4)
    return parser


def create_contact_sheet(input_dir: Path, output_path: Path, *, columns: int = 4) -> dict:
    if columns < 1 or columns > 8:
        raise ValueError("columns must be between 1 and 8")
    pages = sorted(
        (path for path in input_dir.rglob("*") if path.is_file() and path.suffix.casefold() == ".png"),
        key=_page_sort_key,
    )
    if not pages:
        raise ValueError("input directory contains no PNG pages")

    with Image.open(pages[0]) as first_page:
        page_width, page_height = first_page.size
    scale = min(1.0, 360 / max(page_width, 1))
    tile_width = max(1, round(page_width * scale))
    tile_height = max(1, round(page_height * scale))
    rows = math.ceil(len(pages) / columns)
    canvas = Image.new(
        "RGB",
        (
            MARGIN + columns * (tile_width + MARGIN),
            MARGIN + rows * (tile_height + LABEL_HEIGHT + MARGIN),
        ),
        BACKGROUND,
    )
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    entries: list[dict[str, object]] = []
    for index, page_path in enumerate(pages, start=1):
        column = (index - 1) % columns
        row = (index - 1) // columns
        left = MARGIN + column * (tile_width + MARGIN)
        top = MARGIN + row * (tile_height + LABEL_HEIGHT + MARGIN)
        with Image.open(page_path) as page:
            image = page.convert("RGB").resize((tile_width, tile_height), Image.Resampling.LANCZOS)
        canvas.paste(image, (left, top))
        draw.rectangle((left, top, left + tile_width - 1, top + tile_height - 1), outline=BORDER, width=1)
        label = f"Slide {index}: {page_path.name}"
        draw.text((left, top + tile_height + 6), label, fill="#1F2933", font=font)
        entries.append({"index": index, "name": page_path.name, "relative_path": page_path.relative_to(input_dir).as_posix()})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    report = {
        "contact_sheet_version": "1.0",
        "pass": True,
        "input_dir": str(input_dir.resolve()),
        "output": str(output_path.resolve()),
        "columns": columns,
        "page_count": len(entries),
        "pages": entries,
    }
    output_path.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _page_sort_key(path: Path) -> tuple[int, str]:
    digits = "".join(character for character in path.stem if character.isdigit())
    return (int(digits) if digits else 10**9, path.name.casefold())


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = create_contact_sheet(args.input_dir, args.output, columns=args.columns)
    print(f"contact sheet: {report['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
