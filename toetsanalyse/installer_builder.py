from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from .branding import write_windows_icon
from .version import APP_VERSION

APP_NAME = "ToetsVizier"
APP_ICON_NAME = "ToetsVizier.ico"
INSTALLER_NAME_TEMPLATE = "ToetsVizier-{version}-windows-installer.exe"


class InstallerBuildError(RuntimeError):
    pass


def installer_output_name(version: str) -> str:
    return INSTALLER_NAME_TEMPLATE.format(version=str(version).strip())


def installer_output_path(output_dir: Path | str, version: str) -> Path:
    return Path(output_dir) / installer_output_name(version)


def build_root(base_drive: str | None = None) -> Path:
    if base_drive:
        drive = Path(base_drive).anchor or base_drive
        return Path(drive) / "tv-installer-build"
    system_drive = os.environ.get("SystemDrive", "").strip()
    if system_drive:
        return Path(system_drive + "\\") / "tv-installer-build"
    return Path("C:\\tv-installer-build")


def inno_setup_candidates(environ: Mapping[str, str] | None = None) -> list[Path]:
    env = os.environ if environ is None else environ
    local_appdata = str(env.get("LOCALAPPDATA", "")).strip()
    candidates = [
        Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
        Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    ]
    if local_appdata:
        candidates.append(Path(local_appdata) / "Programs" / "Inno Setup 6" / "ISCC.exe")
    return candidates


def find_inno_setup_compiler(environ: Mapping[str, str] | None = None) -> Path:
    for candidate in inno_setup_candidates(environ):
        if candidate.exists():
            return candidate
    raise InstallerBuildError(
        "Inno Setup is niet gevonden. Installeer eerst Inno Setup 6 op deze build-pc."
    )


def playwright_bundle_candidates(environ: Mapping[str, str] | None = None) -> list[Path]:
    env = os.environ if environ is None else environ
    candidates: list[Path] = []
    explicit = str(env.get("PLAYWRIGHT_BROWSERS_PATH", "")).strip()
    if explicit and explicit != "0":
        candidates.append(Path(explicit))
    local_appdata = str(env.get("LOCALAPPDATA", "")).strip()
    if local_appdata:
        candidates.append(Path(local_appdata) / "ms-playwright")
    user_profile = str(env.get("USERPROFILE", "")).strip()
    if user_profile:
        candidates.append(Path(user_profile) / "AppData" / "Local" / "ms-playwright")
    return candidates


def find_playwright_bundle(environ: Mapping[str, str] | None = None) -> Path:
    for candidate in playwright_bundle_candidates(environ):
        if candidate.exists() and any(candidate.glob("chromium-*")):
            return candidate
    raise InstallerBuildError(
        "De Playwright-browsermap is niet gevonden. Voer eerst 'python -m playwright install chromium' uit."
    )


def compute_sha256(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(command: Sequence[str], *, cwd: Path | str) -> None:
    result = subprocess.run(command, cwd=str(cwd), check=False)
    if result.returncode != 0:
        raise InstallerBuildError(f"Opdracht mislukt met exitcode {result.returncode}: {' '.join(command)}")


def build_pyinstaller_output(source_root: Path, dist_dir: Path, work_dir: Path) -> Path:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    run_command(
        [
            "python",
            "-m",
            "PyInstaller",
            "ToetsVizier.spec",
            "--noconfirm",
            "--distpath",
            str(dist_dir),
            "--workpath",
            str(work_dir),
        ],
        cwd=source_root,
    )
    built = dist_dir / APP_NAME
    if not (built / f"{APP_NAME}.exe").exists():
        raise InstallerBuildError("De PyInstaller-build is niet compleet: ToetsVizier.exe ontbreekt.")
    return built


def stage_installer_tree(source_root: Path, build_dir: Path) -> Path:
    dist_dir = build_dir / "dist"
    work_dir = build_dir / "work"
    stage_dir = build_dir / "stage" / APP_NAME
    pyinstaller_dir = build_pyinstaller_output(source_root, dist_dir, work_dir)
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pyinstaller_dir, stage_dir)
    write_windows_icon(stage_dir / APP_ICON_NAME)
    playwright_bundle = find_playwright_bundle()
    shutil.copytree(playwright_bundle, stage_dir / "ms-playwright")
    return stage_dir


def build_installer(
    source_root: Path | str,
    *,
    version: str = APP_VERSION,
    output_dir: Path | str | None = None,
    build_dir: Path | str | None = None,
) -> tuple[Path, str]:
    root = Path(source_root).resolve()
    resolved_output_dir = (Path(output_dir) if output_dir is not None else root / "releases").resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    resolved_build_dir = (Path(build_dir) if build_dir is not None else build_root()).resolve()
    resolved_build_dir.mkdir(parents=True, exist_ok=True)
    stage_dir = stage_installer_tree(root, resolved_build_dir)
    setup_icon_path = write_windows_icon(resolved_build_dir / "toetsvizier.ico")
    compiler = find_inno_setup_compiler()
    script_path = root / "packaging" / "ToetsVizier.iss"
    run_command(
        [
            str(compiler),
            f"/DMyAppVersion={version}",
            f"/DSourceDir={stage_dir}",
            f"/DOutputDir={resolved_output_dir}",
            f"/DOutputBaseFilename={installer_output_name(version)[:-4]}",
            f"/DSetupIconFile={setup_icon_path}",
            str(script_path),
        ],
        cwd=root,
    )
    installer_path = installer_output_path(resolved_output_dir, version)
    if not installer_path.exists():
        raise InstallerBuildError("De installer is niet aangemaakt op de verwachte locatie.")
    return installer_path, compute_sha256(installer_path)
