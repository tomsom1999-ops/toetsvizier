from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from .paths import APP_ROOT, BACKUP_DIR


class SelfUpdateError(RuntimeError):
    pass


PROTECTED_UPDATE_PARTS = {
    "data",
    "backups",
    "exports",
    "logs",
    "config",
    "releases",
    ".git",
    ".github",
    "__pycache__",
}

PROTECTED_UPDATE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".xlsx",
    ".xls",
    ".xlsm",
    ".csv",
    ".tsv",
    ".pdf",
    ".log",
}


def installer_extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".exe", ".msi"}:
        raise SelfUpdateError(
            "De updatebron verwijst niet naar een ondersteunde installer (.exe of .msi)."
        )
    return suffix


def update_package_extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    suffix = Path(parsed.path).suffix.lower()
    if suffix != ".zip":
        raise SelfUpdateError("De updatebron verwijst niet naar een ondersteund updatepakket (.zip).")
    return suffix


def _safe_installer_name(version: str, extension: str) -> str:
    sanitized = "".join(
        character
        for character in str(version).strip()
        if character.isalnum() or character in {".", "-", "_"}
    ).strip("._-")
    if not sanitized:
        sanitized = "update"
    return f"ToetsVizier-{sanitized}{extension}"


def _safe_package_name(version: str) -> str:
    sanitized = "".join(
        character
        for character in str(version).strip()
        if character.isalnum() or character in {".", "-", "_"}
    ).strip("._-")
    if not sanitized:
        sanitized = "update"
    return f"ToetsVizier-update-{sanitized}.zip"


def _download_file(
    url: str,
    target_path: Path,
    *,
    expected_sha256: str = "",
    timeout: int = 60,
    chunk_size: int = 1024 * 256,
    progress_callback: callable | None = None,
    user_agent: str = "ToetsVizier-updater",
) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(target_path.suffix + ".part")
    request = urllib.request.Request(url.strip(), headers={"User-Agent": user_agent})
    received = 0
    total_size: int | None = None
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response, temporary_path.open("wb") as handle:
            content_length = response.headers.get("Content-Length", "").strip()
            if content_length.isdigit():
                total_size = int(content_length)
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                handle.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if progress_callback is not None:
                    progress_callback(received, total_size)
        if expected_sha256.strip():
            actual_hash = digest.hexdigest()
            if actual_hash.casefold() != expected_sha256.strip().casefold():
                raise SelfUpdateError(
                    "De gedownloade update komt niet overeen met de verwachte controlehash."
                )
        temporary_path.replace(target_path)
        return target_path
    except urllib.error.URLError as error:
        raise SelfUpdateError(f"De update kon niet worden gedownload: {error.reason}") from error
    except TimeoutError as error:
        raise SelfUpdateError("Het downloaden van de update duurde te lang.") from error
    except OSError as error:
        raise SelfUpdateError(f"De update kon niet worden opgeslagen: {error}") from error
    finally:
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass


def download_update_installer(
    url: str,
    *,
    version: str,
    expected_sha256: str = "",
    timeout: int = 60,
    chunk_size: int = 1024 * 256,
    target_directory: Path | str | None = None,
    progress_callback: callable | None = None,
) -> Path:
    extension = installer_extension_from_url(url)
    destination_dir = (
        Path(target_directory)
        if target_directory is not None
        else Path(tempfile.gettempdir()) / "ToetsVizier-updates"
    )
    target_path = destination_dir / _safe_installer_name(version, extension)
    return _download_file(
        url,
        target_path,
        expected_sha256=expected_sha256,
        timeout=timeout,
        chunk_size=chunk_size,
        progress_callback=progress_callback,
        user_agent=f"ToetsVizier-updater/{version}",
    )


def download_update_package(
    url: str,
    *,
    version: str,
    expected_sha256: str = "",
    timeout: int = 60,
    chunk_size: int = 1024 * 256,
    target_directory: Path | str | None = None,
    progress_callback: callable | None = None,
) -> Path:
    update_package_extension_from_url(url)
    destination_dir = (
        Path(target_directory)
        if target_directory is not None
        else Path(tempfile.gettempdir()) / "ToetsVizier-updates"
    )
    target_path = destination_dir / _safe_package_name(version)
    return _download_file(
        url,
        target_path,
        expected_sha256=expected_sha256,
        timeout=timeout,
        chunk_size=chunk_size,
        progress_callback=progress_callback,
        user_agent=f"ToetsVizier-package-updater/{version}",
    )


def _normalized_zip_path(name: str) -> Path:
    path = Path(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise SelfUpdateError(f"Updatepakket bevat een onveilig pad: {name}")
    return path


def _is_package_manifest(path: Path) -> bool:
    return len(path.parts) == 1 and path.name.casefold() == "manifest.json"


def _is_protected_update_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    if parts & {part.casefold() for part in PROTECTED_UPDATE_PARTS}:
        return True
    return len(path.parts) == 1 and path.suffix.casefold() in PROTECTED_UPDATE_SUFFIXES


def validate_update_package(package_path: Path | str) -> list[Path]:
    package = Path(package_path)
    try:
        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as error:
        raise SelfUpdateError("Het updatepakket is geen geldige ZIP.") from error
    if not names:
        raise SelfUpdateError("Het updatepakket is leeg.")
    paths: list[Path] = []
    for name in names:
        if name.endswith("/"):
            continue
        path = _normalized_zip_path(name)
        if _is_package_manifest(path):
            continue
        if _is_protected_update_path(path):
            raise SelfUpdateError(
                f"Updatepakket bevat een beschermd bestand of map: {path.as_posix()}"
            )
        paths.append(path)
    if not paths:
        raise SelfUpdateError("Het updatepakket bevat geen appbestanden.")
    return paths


def _copy_existing_files_for_backup(app_root: Path, backup_dir: Path, paths: list[Path]) -> None:
    for relative_path in paths:
        source = app_root / relative_path
        if not source.exists() or not source.is_file():
            continue
        target = backup_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _restore_backup(app_root: Path, backup_dir: Path) -> None:
    if not backup_dir.exists():
        return
    for source in sorted(backup_dir.rglob("*")):
        if not source.is_file():
            continue
        relative_path = source.relative_to(backup_dir)
        target = app_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _remove_new_files(app_root: Path, paths: list[Path]) -> None:
    for relative_path in paths:
        target = app_root / relative_path
        try:
            if target.exists() and target.is_file():
                target.unlink()
        except OSError:
            continue


def _powershell_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _write_staged_update_script(
    script_path: Path,
    *,
    root: Path,
    payload_dir: Path,
    backup_files_dir: Path,
    log_path: Path,
    new_files_path: Path,
    app_pid: int | None = None,
) -> None:
    script = f"""
$ErrorActionPreference = 'Stop'
$appProcessId = {int(app_pid or 0)}
if ($appProcessId -gt 0) {{
    try {{
        Wait-Process -Id $appProcessId -Timeout 60 -ErrorAction SilentlyContinue
    }} catch {{
    }}
}}
Start-Sleep -Milliseconds 500
$root = {_powershell_literal(root)}
$payload = {_powershell_literal(payload_dir)}
$backup = {_powershell_literal(backup_files_dir)}
$log = {_powershell_literal(log_path)}
$newFiles = {_powershell_literal(new_files_path)}

function Copy-ItemWithRetry($source, $target) {{
    $lastError = $null
    for ($attempt = 1; $attempt -le 8; $attempt++) {{
        try {{
            Copy-Item -LiteralPath $source -Destination $target -Force
            return
        }} catch {{
            $lastError = $_
            Start-Sleep -Milliseconds 500
        }}
    }}
    if ($lastError) {{
        throw $lastError
    }}
    throw 'Kopieren mislukt.'
}}

function Copy-Tree($from, $to) {{
    if (-not (Test-Path -LiteralPath $from)) {{
        return
    }}
    Get-ChildItem -LiteralPath $from -Recurse -File | ForEach-Object {{
        $relative = $_.FullName.Substring($from.Length).TrimStart('\\')
        $target = Join-Path $to $relative
        $targetDirectory = Split-Path -Parent $target
        if ($targetDirectory) {{
            New-Item -ItemType Directory -Force -Path $targetDirectory | Out-Null
        }}
        Copy-ItemWithRetry $_.FullName $target
    }}
}}

function Remove-NewFiles($listPath, $rootPath) {{
    if (-not (Test-Path -LiteralPath $listPath)) {{
        return
    }}
    Get-Content -LiteralPath $listPath | ForEach-Object {{
        $relative = $_.Trim()
        if ($relative) {{
            $target = Join-Path $rootPath $relative
            if (Test-Path -LiteralPath $target -PathType Leaf) {{
                Remove-Item -LiteralPath $target -Force
            }}
        }}
    }}
}}

try {{
    Copy-Tree $payload $root
    Add-Content -LiteralPath $log -Value 'Updatepakket toegepast.'
}} catch {{
    Add-Content -LiteralPath $log -Value ('Updatepakket mislukt: ' + $_.Exception.Message)
    try {{
        Copy-Tree $backup $root
        Remove-NewFiles $newFiles $root
        Add-Content -LiteralPath $log -Value 'Back-up teruggezet.'
    }} catch {{
        Add-Content -LiteralPath $log -Value ('Terugzetten van back-up mislukt: ' + $_.Exception.Message)
    }}
    exit 1
}}

$exe = Join-Path $root 'ToetsVizier.exe'
if (Test-Path -LiteralPath $exe) {{
    Start-Process -FilePath $exe
}}
"""
    script_path.write_text(script.strip() + "\n", encoding="utf-8")


def stage_update_package_for_restart(
    package_path: Path | str,
    *,
    app_root: Path | str | None = None,
    backup_root: Path | str | None = None,
    staging_root: Path | str | None = None,
) -> tuple[Path, Path]:
    root = Path(app_root) if app_root is not None else APP_ROOT
    root = root.resolve()
    paths = validate_update_package(package_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups_base = (
        Path(backup_root)
        if backup_root is not None
        else BACKUP_DIR / "updates"
    )
    backup_dir = backups_base / f"voor-updatepakket-{stamp}"
    backup_files_dir = backup_dir / "files"
    backup_dir.mkdir(parents=True, exist_ok=True)
    _copy_existing_files_for_backup(root, backup_files_dir, paths)
    new_paths = [path for path in paths if not (root / path).exists()]

    stage_base = (
        Path(staging_root)
        if staging_root is not None
        else Path(tempfile.gettempdir()) / "ToetsVizier-updates"
    )
    stage_dir = stage_base / f"staged-update-{stamp}"
    payload_dir = stage_dir / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            relative_path = _normalized_zip_path(member.filename)
            if _is_package_manifest(relative_path):
                continue
            if _is_protected_update_path(relative_path):
                raise SelfUpdateError(
                    f"Updatepakket bevat een beschermd bestand of map: {relative_path.as_posix()}"
                )
            target = payload_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)
    manifest = {
        "package": str(Path(package_path).name),
        "app_root": str(root),
        "payload": str(payload_dir),
        "files": [path.as_posix() for path in paths],
        "new_files": [path.as_posix() for path in new_paths],
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    new_files_path = stage_dir / "new-files.txt"
    new_files_path.write_text(
        "\n".join(path.as_posix() for path in new_paths) + ("\n" if new_paths else ""),
        encoding="utf-8",
    )
    script_path = stage_dir / "apply-update.ps1"
    _write_staged_update_script(
        script_path,
        root=root,
        payload_dir=payload_dir,
        backup_files_dir=backup_files_dir,
        log_path=backup_dir / "apply.log",
        new_files_path=new_files_path,
        app_pid=os.getpid(),
    )
    return script_path, backup_dir


def launch_staged_update(script_path: Path | str) -> None:
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(Path(script_path)),
            ],
            close_fds=True,
        )
    except OSError as error:
        raise SelfUpdateError(f"Het updatepakket kon niet worden gestart: {error}") from error


def apply_update_package(
    package_path: Path | str,
    *,
    app_root: Path | str | None = None,
    backup_root: Path | str | None = None,
) -> Path:
    root = Path(app_root) if app_root is not None else APP_ROOT
    root = root.resolve()
    if not root.exists():
        raise SelfUpdateError(f"Appmap bestaat niet: {root}")
    paths = validate_update_package(package_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backups_base = (
        Path(backup_root)
        if backup_root is not None
        else BACKUP_DIR / "updates"
    )
    backup_dir = backups_base / f"voor-updatepakket-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    new_paths = [path for path in paths if not (root / path).exists()]
    manifest = {
        "package": str(Path(package_path).name),
        "app_root": str(root),
        "files": [path.as_posix() for path in paths],
        "new_files": [path.as_posix() for path in new_paths],
    }
    (backup_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    try:
        _copy_existing_files_for_backup(root, backup_dir / "files", paths)
        with zipfile.ZipFile(package_path) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                relative_path = _normalized_zip_path(member.filename)
                if _is_package_manifest(relative_path):
                    continue
                if _is_protected_update_path(relative_path):
                    raise SelfUpdateError(
                        f"Updatepakket bevat een beschermd bestand of map: {relative_path.as_posix()}"
                    )
                target = root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination)
        return backup_dir
    except Exception:
        _restore_backup(root, backup_dir / "files")
        _remove_new_files(root, new_paths)
        raise


def build_installer_launch_command(installer_path: Path | str) -> list[str]:
    installer = Path(installer_path)
    extension = installer.suffix.lower()
    if extension == ".msi":
        return ["msiexec.exe", "/i", str(installer)]
    elif extension == ".exe":
        return [str(installer)]
    else:
        raise SelfUpdateError("Alleen .exe- en .msi-installers kunnen automatisch worden gestart.")


def launch_installer(installer_path: Path | str) -> None:
    command = build_installer_launch_command(installer_path)
    try:
        if installer_extension_from_url(str(installer_path)) == ".exe" and hasattr(os, "startfile"):
            os.startfile(str(Path(installer_path)))
            return
        subprocess.Popen(command, close_fds=True)
    except OSError as error:
        raise SelfUpdateError(f"De installer kon niet worden gestart: {error}") from error
