"""Bundle a checked patch ZIP into a standalone updater (requires PyInstaller)."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from standalone_updater import inspect_package


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('package', type=Path)
    parser.add_argument('--output-dir', type=Path, default=Path('releases'))
    args = parser.parse_args()
    manifest = inspect_package(args.package)
    version = manifest['version']
    if not version or any(c not in '0123456789.-abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in version):
        raise ValueError('Ongeldig versienummer.')
    output = args.output_dir.resolve()
    with tempfile.TemporaryDirectory(prefix='toetsvizier-updater-') as directory:
        stage = Path(directory)
        shutil.copy2(args.package, stage / 'payload.zip')
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--onefile', '--windowed', '--name', f'ToetsVizier-update-{version}',
            '--distpath', str(output), '--workpath', str(stage / 'build'),
            '--specpath', str(stage), '--add-data', f'{stage / "payload.zip"};.',
            str(Path(__file__).with_name('standalone_updater.py'))], check=True)


if __name__ == '__main__':
    main()
