from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .update_checker import update_info_from_manifest
from .version import APP_VERSION

DEFAULT_TEMPLATE_PATH = Path("packaging") / "update_manifest.source.json"
DEFAULT_OUTPUT_PATH = Path("update.json")
DEFAULT_RELEASE_URL_TEMPLATE = "https://github.com/tomsom1999-ops/toetsvizier/releases/tag/v{version}"
DEFAULT_INSTALLER_URL_TEMPLATE = (
    "https://github.com/tomsom1999-ops/toetsvizier/releases/download/"
    "v{version}/ToetsVizier-{version}-windows-installer.exe"
)
DEFAULT_PACKAGE_URL_TEMPLATE = (
    "https://github.com/tomsom1999-ops/toetsvizier/releases/download/"
    "v{version}/ToetsVizier-update-{version}.zip"
)


class UpdateManifestError(ValueError):
    pass


def _replace_version_placeholders(value: object, version: str) -> object:
    if isinstance(value, str):
        return value.replace("{version}", version)
    if isinstance(value, list):
        return [_replace_version_placeholders(item, version) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _replace_version_placeholders(item, version)
            for key, item in value.items()
        }
    return value


def load_manifest_template(path: Path | str) -> dict[str, Any]:
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise UpdateManifestError(f"Sjabloonbestand niet gevonden: {source}") from error
    except json.JSONDecodeError as error:
        raise UpdateManifestError(f"Sjabloonbestand is geen geldige JSON: {source}") from error
    if not isinstance(payload, dict):
        raise UpdateManifestError("Het manifestsjabloon moet een JSON-object zijn.")
    return payload


def build_update_manifest(
    template: dict[str, Any],
    *,
    version: str = APP_VERSION,
    download_url: str | None = None,
    installer_url: str | None = None,
    package_url: str | None = None,
    installer_sha256: str | None = None,
    package_sha256: str | None = None,
    update_type: str | None = None,
) -> dict[str, Any]:
    if not version.strip():
        raise UpdateManifestError("Geef een geldig versienummer op.")
    rendered = _replace_version_placeholders(template, version.strip())
    if not isinstance(rendered, dict):
        raise UpdateManifestError("Het gerenderde manifestsjabloon heeft een ongeldige structuur.")
    rendered_download_template = str(rendered.get("download_url_template") or "").strip()
    rendered_installer_template = str(rendered.get("installer_url_template") or "").strip()
    rendered_package_template = str(rendered.get("package_url_template") or "").strip()
    resolved_download_url = (
        download_url.strip()
        if download_url is not None and download_url.strip()
        else (rendered_download_template or DEFAULT_RELEASE_URL_TEMPLATE.format(version=version.strip()))
    )
    resolved_installer_url = (
        installer_url.strip()
        if installer_url is not None and installer_url.strip()
        else (rendered_installer_template or DEFAULT_INSTALLER_URL_TEMPLATE.format(version=version.strip()))
    )
    version_entries = rendered.get("versions")
    if not isinstance(version_entries, list) or not version_entries:
        raise UpdateManifestError("Neem in het manifestsjabloon minstens één versie-item op.")
    if not any(str(entry.get("version") or "").strip() == version.strip() for entry in version_entries if isinstance(entry, dict)):
        raise UpdateManifestError(
            f"Het manifestsjabloon bevat geen versie-item voor versie {version.strip()}."
        )
    manifest = {
        "latest_version": version.strip(),
        "download_url": resolved_download_url,
        "installer_url": resolved_installer_url,
        "release_notes": str(rendered.get("release_notes") or "").strip(),
        "versions": version_entries,
    }
    resolved_update_type = (
        update_type.strip().casefold()
        if update_type is not None and update_type.strip()
        else str(rendered.get("update_type") or "").strip().casefold()
    )
    resolved_package_url = (
        package_url.strip()
        if package_url is not None and package_url.strip()
        else rendered_package_template
    )
    if resolved_update_type == "package" and not resolved_package_url:
        resolved_package_url = DEFAULT_PACKAGE_URL_TEMPLATE
    if resolved_package_url:
        resolved_package_url = resolved_package_url.format(version=version.strip())
    if resolved_package_url:
        manifest["package_url"] = resolved_package_url
    if resolved_update_type:
        manifest["update_type"] = resolved_update_type
    resolved_sha256 = (
        installer_sha256.strip()
        if installer_sha256 is not None and installer_sha256.strip()
        else str(rendered.get("installer_sha256") or "").strip()
    )
    if resolved_sha256:
        manifest["installer_sha256"] = resolved_sha256
    resolved_package_sha256 = (
        package_sha256.strip()
        if package_sha256 is not None and package_sha256.strip()
        else str(rendered.get("package_sha256") or "").strip()
    )
    if resolved_package_sha256:
        manifest["package_sha256"] = resolved_package_sha256
    update_info_from_manifest(manifest, current_version=version.strip())
    return manifest


def write_update_manifest(path: Path | str, manifest: dict[str, Any]) -> Path:
    target = Path(path)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return target


def _normalized_json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genereer of controleer update.json voor ToetsVizier."
    )
    parser.add_argument(
        "--template",
        default=str(DEFAULT_TEMPLATE_PATH),
        help="Pad naar het manifestsjabloon.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Pad naar het te schrijven updatebestand.",
    )
    parser.add_argument(
        "--version",
        default=APP_VERSION,
        help="Versienummer voor latest_version en de downloadlink.",
    )
    parser.add_argument(
        "--download-url",
        default="",
        help="Expliciete releasepagina. Laat leeg om het sjabloon of de standaard-URL te gebruiken.",
    )
    parser.add_argument(
        "--installer-url",
        default="",
        help="Expliciete directe installerlink (.exe of .msi).",
    )
    parser.add_argument(
        "--package-url",
        default="",
        help="Expliciete directe link naar een updatepakket (.zip).",
    )
    parser.add_argument(
        "--installer-sha256",
        default="",
        help="Optionele SHA-256-controlehash van de installer.",
    )
    parser.add_argument(
        "--package-sha256",
        default="",
        help="Optionele SHA-256-controlehash van het updatepakket.",
    )
    parser.add_argument(
        "--update-type",
        default="",
        choices=["", "installer", "package"],
        help="Voorkeursroute voor deze update.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Controleer of het huidige updatebestand al overeenkomt met de gegenereerde inhoud.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = build_update_manifest(
        load_manifest_template(args.template),
        version=str(args.version),
        download_url=str(args.download_url),
        installer_url=str(args.installer_url),
        package_url=str(args.package_url),
        installer_sha256=str(args.installer_sha256),
        package_sha256=str(args.package_sha256),
        update_type=str(args.update_type),
    )
    output_path = Path(args.output)
    if args.check:
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            print(f"Updatebestand ontbreekt: {output_path}")
            return 1
        except json.JSONDecodeError:
            print(f"Updatebestand is geen geldige JSON: {output_path}")
            return 1
        if _normalized_json(existing) != _normalized_json(manifest):
            print(
                f"Updatebestand is niet bijgewerkt. Genereer opnieuw met: "
                f"python packaging\\build_update_manifest.py --output {output_path}"
            )
            return 1
        print(f"Updatebestand is actueel: {output_path}")
        return 0
    write_update_manifest(output_path, manifest)
    print(f"Updatebestand geschreven: {output_path}")
    return 0
