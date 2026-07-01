from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .version import APP_VERSION


UPDATE_MANIFEST_URL_KEY = "updates/manifest_url"
UPDATE_AUTO_CHECK_KEY = "updates/auto_check_enabled"
DEFAULT_UPDATE_MANIFEST_URL = "https://raw.githubusercontent.com/tomsom1999-ops/toetsvizier/main/update.json"


class UpdateCheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class VersionChange:
    version: str
    title: str = ""
    change_type: str = ""
    changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    download_url: str
    installer_url: str
    package_url: str = ""
    installer_sha256: str = ""
    package_sha256: str = ""
    update_type: str = ""
    release_notes: str = ""
    version_changes: tuple[VersionChange, ...] = ()

    @property
    def is_newer(self) -> bool:
        return version_tuple(self.latest_version) > version_tuple(self.current_version)


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", str(version))[:4]]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts)


def semantic_version_explanation(version: str) -> str:
    parts = version_tuple(version)
    return (
        f"{parts[0]} = grote update, "
        f"{parts[1]} = middelgrote update, "
        f"{parts[2]} = kleine update/patch"
    )


def _text_list(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _version_change_from_value(version: str, value: object) -> VersionChange:
    if isinstance(value, dict):
        return VersionChange(
            version=str(value.get("version") or version).strip(),
            title=str(value.get("title") or value.get("naam") or "").strip(),
            change_type=str(value.get("type") or value.get("soort") or "").strip(),
            changes=_text_list(value.get("changes") or value.get("wijzigingen") or value.get("notes")),
        )
    return VersionChange(version=str(version).strip(), changes=_text_list(value))


def version_changes_from_manifest(manifest: dict[str, object]) -> tuple[VersionChange, ...]:
    raw_changes = manifest.get("versions") or manifest.get("changelog") or manifest.get("release_history")
    if isinstance(raw_changes, dict):
        changes = [_version_change_from_value(version, value) for version, value in raw_changes.items()]
    elif isinstance(raw_changes, list):
        changes = [
            _version_change_from_value(str(index + 1), value)
            for index, value in enumerate(raw_changes)
        ]
    else:
        changes = []
    return tuple(
        sorted(
            (change for change in changes if change.version),
            key=lambda change: version_tuple(change.version),
            reverse=True,
        )
    )


def update_info_from_manifest(
    manifest: dict[str, object],
    *,
    current_version: str = APP_VERSION,
) -> UpdateInfo:
    latest_version = str(manifest.get("latest_version") or manifest.get("version") or "").strip()
    download_url = str(
        manifest.get("download_url")
        or manifest.get("release_url")
        or manifest.get("url")
        or ""
    ).strip()
    package_url = str(
        manifest.get("package_url")
        or manifest.get("update_package_url")
        or manifest.get("patch_url")
        or ""
    ).strip()
    installer_url = str(manifest.get("installer_url") or "").strip()
    if not installer_url and not package_url:
        installer_url = str(manifest.get("download_url") or manifest.get("url") or "").strip()
    installer_sha256 = str(manifest.get("installer_sha256") or manifest.get("sha256") or "").strip()
    package_sha256 = str(
        manifest.get("package_sha256")
        or manifest.get("update_package_sha256")
        or manifest.get("patch_sha256")
        or ""
    ).strip()
    update_type = str(
        manifest.get("update_type")
        or manifest.get("update_kind")
        or ("package" if package_url else "installer")
    ).strip().casefold()
    release_notes = str(manifest.get("release_notes") or manifest.get("notes") or "").strip()
    if not latest_version:
        raise UpdateCheckError("Het updatebestand bevat geen nieuwste versienummer.")
    if not installer_url and not package_url:
        raise UpdateCheckError("Het updatebestand bevat geen installerlink of updatepakketlink.")
    if not download_url:
        download_url = package_url or installer_url
    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        download_url=download_url,
        installer_url=installer_url,
        package_url=package_url,
        installer_sha256=installer_sha256,
        package_sha256=package_sha256,
        update_type=update_type,
        release_notes=release_notes,
        version_changes=version_changes_from_manifest(manifest),
    )


def check_for_update(
    manifest_url: str,
    *,
    current_version: str = APP_VERSION,
    timeout: int = 8,
) -> UpdateInfo:
    url = manifest_url.strip()
    if not url:
        raise UpdateCheckError("Er is nog geen updatebron ingesteld.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"ToetsVizier/{current_version}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.URLError as error:
        raise UpdateCheckError(f"De updatebron kon niet worden bereikt: {error.reason}") from error
    except TimeoutError as error:
        raise UpdateCheckError("De updatecontrole duurde te lang.") from error

    try:
        manifest = json.loads(payload)
    except json.JSONDecodeError as error:
        raise UpdateCheckError("Het updatebestand is geen geldig JSON-bestand.") from error
    if not isinstance(manifest, dict):
        raise UpdateCheckError("Het updatebestand heeft een onbekende structuur.")
    return update_info_from_manifest(manifest, current_version=current_version)
