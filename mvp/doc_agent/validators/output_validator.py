from __future__ import annotations

from pathlib import Path


class OutputValidator:
    def validate(self, path: str | Path, target: str) -> list[str]:
        output_path = Path(path)
        errors: list[str] = []
        if not output_path.exists():
            return [f"Output file does not exist: {output_path}"]
        if output_path.stat().st_size <= 0:
            errors.append(f"Output file is empty: {output_path}")
        if output_path.suffix.lower() != f".{target}":
            errors.append(f"Output suffix {output_path.suffix} does not match target {target}")
        if target == "pptx":
            try:
                from pptx import Presentation

                Presentation(str(output_path))
            except Exception as exc:
                errors.append(f"PPTX cannot be opened: {exc}")
        elif target == "docx":
            try:
                from docx import Document

                Document(str(output_path))
            except Exception as exc:
                errors.append(f"DOCX cannot be opened: {exc}")
        else:
            errors.append(f"Unsupported target: {target}")
        return errors
