from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "desktop" / "DocumentWorkbench" / "Assets" / "app-icon.ico"


def main() -> int:
    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((16, 16, 240, 240), radius=42, fill="#202328")
    draw.rounded_rectangle((58, 38, 198, 218), radius=12, fill="#FFFFFF")
    draw.polygon([(158, 38), (198, 78), (158, 78)], fill="#DADDE3")
    draw.rectangle((79, 103, 177, 116), fill="#C7002B")
    draw.rounded_rectangle((79, 137, 177, 148), radius=5, fill="#747A83")
    draw.rounded_rectangle((79, 166, 155, 177), radius=5, fill="#A3A8B0")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(
        OUTPUT,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(OUTPUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
