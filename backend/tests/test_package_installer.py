from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts import package_installer


@pytest.mark.parametrize(
    "member_name",
    [
        "bundle/../../outside.txt",
        "/absolute.txt",
        "bundle\\..\\outside.txt",
    ],
)
def test_portable_zip_extraction_rejects_path_traversal(tmp_path: Path, member_name: str) -> None:
    archive = tmp_path / "malicious.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr(member_name, b"unsafe")

    with pytest.raises(SystemExit, match="unsafe member path"):
        package_installer._extract_zip(archive, destination)

    assert not (tmp_path / "outside.txt").exists()
    assert not (destination / "outside.txt").exists()


def test_portable_zip_extraction_rejects_duplicate_casefolded_targets(tmp_path: Path) -> None:
    archive = tmp_path / "duplicate.zip"
    destination = tmp_path / "staging"
    destination.mkdir()
    with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
        bundle.writestr("bundle/DocumentWorkbench.exe", b"first")
        bundle.writestr("bundle/documentworkbench.exe", b"second")

    with pytest.raises(SystemExit, match="duplicate extraction targets"):
        package_installer._extract_zip(archive, destination)

    assert (destination / "DocumentWorkbench.exe").read_bytes() == b"first"
