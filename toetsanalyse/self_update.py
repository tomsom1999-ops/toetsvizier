from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class SelfUpdateError(RuntimeError):
    pass


def installer_extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".exe", ".msi"}:
        raise SelfUpdateError(
            "De updatebron verwijst niet naar een ondersteunde installer (.exe of .msi)."
        )
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
    destination_dir.mkdir(parents=True, exist_ok=True)
    target_path = destination_dir / _safe_installer_name(version, extension)
    temporary_path = target_path.with_suffix(target_path.suffix + ".part")
    request = urllib.request.Request(
        url.strip(),
        headers={"User-Agent": f"ToetsVizier-updater/{version}"},
    )
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
