from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare approved Windows Office PNG baselines with candidate exports.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pixel-delta", type=int, default=24)
    parser.add_argument("--max-different-ratio", type=float, default=0.01)
    parser.add_argument("--max-mean-delta", type=float, default=3.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = compare_png_sets(
        args.baseline,
        args.candidate,
        pixel_delta=args.pixel_delta,
        max_different_ratio=args.max_different_ratio,
        max_mean_delta=args.max_mean_delta,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"visual diff: {args.output}")
    return 0 if report["pass"] else 1


def compare_png_sets(
    baseline_dir: Path,
    candidate_dir: Path,
    *,
    pixel_delta: int,
    max_different_ratio: float,
    max_mean_delta: float,
) -> dict:
    baseline = _pngs(baseline_dir)
    candidate = _pngs(candidate_dir)
    names = sorted(set(baseline) | set(candidate))
    slides = []
    for name in names:
        if name not in baseline or name not in candidate:
            slides.append({"name": name, "pass": False, "reason": "baseline_or_candidate_missing"})
            continue
        slides.append(
            _compare_png(
                name,
                baseline[name],
                candidate[name],
                pixel_delta=pixel_delta,
                max_different_ratio=max_different_ratio,
                max_mean_delta=max_mean_delta,
            )
        )
    return {
        "visual_diff_version": "1.0",
        "pass": bool(slides) and all(slide["pass"] for slide in slides),
        "baseline": str(baseline_dir),
        "candidate": str(candidate_dir),
        "thresholds": {
            "pixel_delta": pixel_delta,
            "max_different_ratio": max_different_ratio,
            "max_mean_delta": max_mean_delta,
        },
        "slides": slides,
    }


def _pngs(root: Path) -> dict[str, Path]:
    return {path.relative_to(root).as_posix(): path for path in root.rglob("*.png")}


def _compare_png(
    name: str,
    baseline: Path,
    candidate: Path,
    *,
    pixel_delta: int,
    max_different_ratio: float,
    max_mean_delta: float,
) -> dict:
    with Image.open(baseline) as left_source, Image.open(candidate) as right_source:
        left = left_source.convert("RGB")
        right = right_source.convert("RGB")
        if left.size != right.size:
            return {"name": name, "pass": False, "reason": "image_size_mismatch", "baseline_size": left.size, "candidate_size": right.size}
        difference = ImageChops.difference(left, right)
        channels = difference.split()
        maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
        changed = maximum.point(lambda value: 255 if value > pixel_delta else 0).histogram()[255]
        ratio = changed / (left.width * left.height)
        mean_delta = sum(ImageStat.Stat(difference).mean) / 3
    passed = ratio <= max_different_ratio and mean_delta <= max_mean_delta
    return {
        "name": name,
        "pass": passed,
        "different_ratio": round(ratio, 6),
        "mean_delta": round(mean_delta, 4),
    }


if __name__ == "__main__":
    raise SystemExit(main())
