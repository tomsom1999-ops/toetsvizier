"""Small Windows updater; bundled with payload.zip by build_patch_exe.py."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import zipfile


def inspect_package(package):
    with zipfile.ZipFile(package) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        files = manifest['files']
        hashes = manifest['sha256']
        if not files or len({name.casefold() for name in files}) != len(files):
            raise ValueError('Ongeldige bestandslijst.')
        if sorted(archive.namelist()) != sorted(['manifest.json', *files]):
            raise ValueError('De inhoud wijkt af van de bestandslijst.')
        for name in files:
            path = PureWindowsPath(name)
            if (path.is_absolute() or path.drive or '..' in path.parts or ':' in name
                    or any(part.casefold() in {'data', 'backups', 'config', 'exports', 'logs'} for part in path.parts)
                    or path.suffix.casefold() in {'.db', '.sqlite', '.sqlite3', '.tviz'}):
                raise ValueError(f'Beschermd of ongeldig pad: {name}')
            digest = hashlib.sha256(archive.read(name)).hexdigest()
            if digest.casefold() != hashes[name].casefold():
                raise ValueError(f'Bestand beschadigd: {name}')
        return manifest


def find_installation():
    candidates = []
    if sys.platform == 'win32':
        import winreg
        key = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\{E55D8EE5-4370-4C66-B0AF-1489A3B6169E}_is1'
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key) as handle:
                    candidates.append(Path(winreg.QueryValueEx(handle, 'InstallLocation')[0]))
            except OSError:
                pass
    candidates.append(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'ToetsVizier')
    return next((path for path in candidates if (path / 'ToetsVizier.exe').is_file()), None)


def apply_patch(package, root, backup):
    manifest = inspect_package(package)
    root = Path(root).resolve()
    if not (root / 'ToetsVizier.exe').is_file():
        raise ValueError('Kies de bestaande ToetsVizier-installatiemap.')
    files = manifest['files']
    # Refuse junctions/symlinks leading outside the installation.
    for name in files:
        (root / name).resolve().relative_to(root)
    for name, expected in manifest.get('baseline_sha256', {}).items():
        target = (root / name).resolve()
        target.relative_to(root)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest().casefold() != expected.casefold():
            raise ValueError('Deze patch past niet bij de geïnstalleerde programmaversie. Gebruik een passend updatepakket.')
    backup = Path(backup)
    backup.mkdir(parents=True, exist_ok=False)
    existing = []
    for name in files:
        target = root / name
        if target.exists():
            saved = backup / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, saved)
            existing.append(name)
    touched = []
    try:
        with zipfile.ZipFile(package) as archive:
            for name in files:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                touched.append(name)
                with archive.open(name) as source, target.open('wb') as destination:
                    shutil.copyfileobj(source, destination)
                if hashlib.sha256(target.read_bytes()).hexdigest().casefold() != manifest['sha256'][name].casefold():
                    raise ValueError(f'Controle na kopiëren mislukt: {name}')
    except Exception as error:
        try:
            for name in reversed(touched):
                if name in existing:
                    shutil.copy2(backup / name, root / name)
                else:
                    (root / name).unlink(missing_ok=True)
        except Exception as restore_error:
            raise RuntimeError(f'Update en herstel mislukt. Back-up: {backup}. {restore_error}') from error
        raise RuntimeError(f'Update mislukt; vorige bestanden hersteld. {error}') from error
    return manifest


def main():
    import argparse
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from datetime import datetime
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path)
    parser.add_argument('--root', type=Path)
    parser.add_argument('--wait-pid', type=int, default=0)
    parser.add_argument('--check', action='store_true', help='Controleer het pakket zonder bestanden te wijzigen.')
    args = parser.parse_args()
    if args.check:
        package = args.package or Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'payload.zip'
        inspect_package(package)
        return
    window = tk.Tk()
    window.title('ToetsVizier bijwerken')
    window.geometry('480x150')
    status = tk.StringVar(value='Update controleren…')
    tk.Label(window, textvariable=status, wraplength=440, padx=20, pady=25).pack()
    window.update()
    package = args.package or Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'payload.zip'
    try:
        manifest = inspect_package(package)
        root = args.root or find_installation()
        if root is None:
            selected = filedialog.askdirectory(title='Kies de bestaande ToetsVizier-installatiemap')
            if not selected:
                return
            root = Path(selected)
        if not args.wait_pid and not messagebox.askokcancel('ToetsVizier bijwerken',
                f"Update naar {manifest['version']}\n\nInstallatie: {root}\n\n"
                'Sluit ToetsVizier voordat je op OK klikt. Je toetsen en resultaten blijven bewaard.'):
            return
        if args.wait_pid:
            import ctypes
            import time
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            handle = kernel.OpenProcess(0x100000, False, args.wait_pid)
            if not handle:
                if ctypes.get_last_error() != 87:
                    raise RuntimeError('Kan niet controleren of ToetsVizier is afgesloten.')
            else:
                try:
                    deadline = time.monotonic() + 120
                    status.set('Wachten totdat ToetsVizier is afgesloten. Rond eventuele opslagvragen af.')
                    while True:
                        wait_result = kernel.WaitForSingleObject(handle, 0)
                        if wait_result == 0:
                            break
                        if wait_result != 258:
                            raise RuntimeError('Afsluiten van ToetsVizier kon niet worden bevestigd.')
                        if time.monotonic() >= deadline:
                            raise RuntimeError('ToetsVizier is nog geopend. Er zijn geen bestanden gewijzigd. Probeer de update opnieuw nadat de app gesloten is.')
                        window.update()
                        time.sleep(0.1)
                finally:
                    kernel.CloseHandle(handle)
        status.set('Back-up maken en update toepassen…')
        window.update()
        backup = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'ToetsVizier' / 'backups' / 'updates' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        apply_patch(package, root, backup)
        if messagebox.askyesno('Update voltooid', f"ToetsVizier {manifest['version']} is bijgewerkt.\nBack-up: {backup}\n\nToetsVizier starten?"):
            subprocess.Popen([str(root / 'ToetsVizier.exe')], cwd=root)
    except Exception as error:
        messagebox.showerror('Update niet voltooid', str(error))
    finally:
        window.destroy()


if __name__ == '__main__':
    main()
