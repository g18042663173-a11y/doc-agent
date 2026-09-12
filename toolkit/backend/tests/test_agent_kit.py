from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

import pytest

from scripts.install_agent_kit import check_kit, install_kit
from scripts import package_huawei_doc_skill as generation, package_rhetoric_deck_skill as imitation
from scripts.portable_skill_install import install, read_archive_manifest, verify_directory
from scripts.portable_skill_runtime import isolated_environment, run_skill, sha256


@pytest.fixture(scope="module")
def portable_archives():
    # A short outside-repository path also models a real extracted handoff.
    with tempfile.TemporaryDirectory(prefix="agent-kit-") as temporary:
        root = Path(temporary)
        for packager, short in ((generation, "生成.zip"), (imitation, "模仿.zip")):
            if packager is generation:
                archive, _ = packager.build_archive(root, overwrite=False)
            else:
                archive, _ = packager.build_archive(root, packager.verify_skill_source(), overwrite=False)
            destination = root / short
            archive.rename(destination)
            destination.with_suffix(".zip.sha256").write_text(f"{sha256(destination)}  {short}\n", encoding="utf-8")
        yield root


def test_install_agent_kit_copies_both_skills_without_docker(portable_archives):
    destination = portable_archives / "installed"
    report = install_kit(destination, zip_dir=portable_archives)
    assert report["docker_required"] is False
    assert "package_document_workbench.py" in report["workbench"]
    assert {item["name"] for item in report["skills"]} == {generation.SKILL_NAME, imitation.SKILL_NAME}
    assert {item["version"] for item in report["skills"]} == {generation.SKILL_VERSION, imitation.SKILL_VERSION}
    for name in (generation.SKILL_NAME, imitation.SKILL_NAME):
        manifest = verify_directory(destination / name)
        assert manifest["dependency_bundle_included"] is True
        assert (destination / name / "runtime/python/python.exe").is_file()


def test_check_agent_kit_runs_packaged_doctors_and_reads_actual_versions(portable_archives):
    destination = portable_archives / "check"
    install_kit(destination, zip_dir=portable_archives)
    report = check_kit(destination, python=Path("intentionally-missing-system-python.exe"))
    assert report["ok"] is True
    assert all(item["doctor"] == "ok" for item in report["skills"])
    assert {item["version"] for item in report["skills"]} == {generation.SKILL_VERSION, imitation.SKILL_VERSION}


def test_each_extracted_installer_runs_without_repository_or_system_python(portable_archives):
    external = portable_archives / "中文 空格"
    external.mkdir()
    for short in ("生成.zip", "模仿.zip"):
        archive = portable_archives / short
        manifest = read_archive_manifest(archive)
        with zipfile.ZipFile(archive) as package:
            package.extractall(external)
        source = external / manifest["skill_name"]
        runtime = json.loads(run_skill(source, "--verify-runtime", cwd=external).stdout)
        assert runtime["network_blocked"] is True
        assert runtime["version"] == "3.12.10"
        assert all(str(source / "runtime/python") in path for path in runtime["sys_path"])
        installed = external / "skills"
        result = subprocess.run([str(source / "runtime/python/python.exe"), "-I", "-X", "utf8", "-B",
            str(source / "portable_install.py"), "--dest", str(installed)], cwd=external,
            env=isolated_environment(), capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert result.returncode == 0, result.stderr or result.stdout
        payload = json.loads(result.stdout)
        assert payload["version"] == manifest["skill_version"]
        verify_directory(installed / manifest["skill_name"])


def test_corrupt_archive_never_removes_previous_install(portable_archives):
    destination = portable_archives / "retained"
    install_kit(destination, zip_dir=portable_archives)
    marker = destination / imitation.SKILL_NAME / "VERSION"
    original = marker.read_bytes()
    corrupt = portable_archives / "corrupt.zip"
    with zipfile.ZipFile(portable_archives / "模仿.zip") as source, zipfile.ZipFile(corrupt, "w") as target:
        for info in source.infolist():
            value = b"tampered" if info.filename.endswith("/VERSION") else source.read(info.filename)
            target.writestr(info, value)
    with pytest.raises(ValueError, match="hash mismatch"):
        install(corrupt, destination)
    assert marker.read_bytes() == original


def test_doctor_failure_preserves_previous_install(portable_archives, monkeypatch):
    from scripts import portable_skill_install
    destination = portable_archives / "doctor-failure"
    install_kit(destination, zip_dir=portable_archives)
    previous = sha256(destination / imitation.SKILL_NAME / "VERSION")
    def fail(_directory):
        raise ValueError("doctor deliberately failed")
    monkeypatch.setattr(portable_skill_install, "doctor", fail)
    with pytest.raises(ValueError, match="doctor deliberately failed"):
        install(portable_archives / "模仿.zip", destination)
    assert sha256(destination / imitation.SKILL_NAME / "VERSION") == previous


def test_reinstall_keeps_verified_previous_install_backup(portable_archives):
    destination = portable_archives / "backup-success"
    archive = portable_archives / "模仿.zip"
    install(archive, destination)
    result = install(archive, destination)
    backup = Path(result["previous_install_backup"])
    assert backup.parent == destination / ".backups"
    assert verify_directory(backup) == verify_directory(destination / imitation.SKILL_NAME)


def test_backup_relocation_failure_retains_recovery_copy(portable_archives, monkeypatch):
    destination = portable_archives / "backup-failure"
    archive = portable_archives / "模仿.zip"
    install(archive, destination)
    original_rename = Path.rename
    def fail_backup_rename(path, target):
        if path.name == "previous":
            raise OSError("backup relocation deliberately failed")
        return original_rename(path, target)
    monkeypatch.setattr(Path, "rename", fail_backup_rename)
    with pytest.raises(RuntimeError, match="Previous install retained for recovery"):
        install(archive, destination)
    backups = list(destination.glob(".install-*/previous"))
    assert len(backups) == 1
    assert verify_directory(backups[0]) == verify_directory(destination / imitation.SKILL_NAME)


def test_stale_short_name_checksum_blocks_both_installs(portable_archives):
    bad = portable_archives / "bad-short-name"
    bad.mkdir()
    for short in ("生成.zip", "模仿.zip"):
        shutil.copy2(portable_archives / short, bad / short)
        shutil.copy2((portable_archives / short).with_suffix(".zip.sha256"), (bad / short).with_suffix(".zip.sha256"))
    (bad / "模仿.zip.sha256").write_text("0" * 64 + "  模仿.zip\n", encoding="utf-8")
    destination = portable_archives / "not-installed"
    with pytest.raises(ValueError, match="digest mismatch"):
        install_kit(destination, zip_dir=bad)
    assert not destination.exists()


@pytest.mark.parametrize("member", ["../escape.py", "/absolute.py", "skill/C:/escape.py"])
def test_install_rejects_unsafe_archive_members(tmp_path, member):
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr(member, "malicious")
    with pytest.raises(ValueError, match="unsafe package path"):
        read_archive_manifest(archive)


def test_package_path_validator_rejects_backslash_before_io():
    # ZipInfo normalizes Windows separators when a fixture is written/read.
    from scripts.portable_skill_install import _safe_relative
    with pytest.raises(ValueError, match="unsafe package path"):
        _safe_relative("skill\\escape.py")
