#!/usr/bin/env python3
"""
HEAVILY inspired by the Nicotine+ cxfreeze script:
https://github.com/nicotine-plus/nicotine-plus/blob/master/build-aux/windows/setup.py

TODO stop trying to 
"""

import os
import platform
import shutil
import sys
import sysconfig
import tempfile
from pathlib import Path

from cx_Freeze import Executable, setup

if platform.system() != 'Windows':
    raise NotImplementedError('Freezing is only supported on Windows!')

USAGE_MSG = f'\n\nUsage:\n\t{Path(__file__).name} build_dir [dest_dir]'
TYPELIB_PREFIXES = [
    'Gtk-4',
    'Gio-',
    'Gdk-4',
    'GLib-',
    'Gsk-',
    'GObject-',
    'GModule-',
    'GdkPixbuf-',
    'Adw-',
    'Graphene-',
    'HarfBuzz-',
    'Pango-',
    'PangoCairo-',
    'cairo-',
    'freetype2-',
    'GdkWin32-4',
    'GioWin32',
    'GLibWin32',
    'Win32-',
]
base_prefix = Path(os.environ['MSYSTEM_PREFIX'])
if not base_prefix:
    raise ValueError('MSYSTEM_PREFIX environment variable is not set')
lib_dir = base_prefix / 'bin'
lib_ext = '.dll'

pkgconf_path = shutil.which('pkg-config')
if not pkgconf_path:
    raise FileNotFoundError('pkg-config was not found in path (not installed?)')


def freeze(argv: list[str]):
    include_files: list[tuple[Path, Path]] = []
    if len(argv) == 1:
        print('ERROR: No build dir specified!' + USAGE_MSG)
        return
    elif not os.path.isdir(argv[1]):
        print(f'ERROR: "{argv[1]}" is not a directory!' + USAGE_MSG)
        return

    rencher_module = (
        Path(argv[1]) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
    )
    rencher_gres = Path(argv[1]) / 'share' / 'rencher'
    if not rencher_module.is_dir():
        print(f'ERROR: "{argv[1]}" is not valid ("{rencher_module}" does not exist)' + USAGE_MSG)
        return

    loaders_dir = base_prefix / 'lib' / 'gdk-pixbuf-2.0' / '2.10.0'
    pixbuf_path = loaders_dir / 'loaders.cache'
    adw_icon_dir = base_prefix / 'share' / 'icons' / 'Adwaita'

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_pixbuf_path = tmp_dir / 'loaders.cache'
    with open(tmp_pixbuf_path, 'w') as temp_f, open(pixbuf_path) as f:
        data = f.read()
        temp_f.write(data.replace('lib\\\\gdk-pixbuf-2.0\\\\2.10.0\\\\loaders', 'lib'))
    include_files.extend(find_files('loaders.cache', tmp_dir, 'lib'))
    include_files.extend(find_files(f'*.{lib_ext}*', loaders_dir / 'loaders', 'lib'))
    include_files.extend(find_files('*', rencher_module, 'lib', recursive=True))
    include_files.extend(find_files('*', rencher_gres, 'share'))
    include_files.extend(find_files('gdbus.exe', lib_dir, 'lib/'))
    include_files.extend(find_files('*.conf', '/etc/fonts/', 'share/fonts/', True))
    include_files.extend(find_files('libgtk-4*', lib_dir, 'lib/'))
    include_files.extend(find_files('libadwaita-1*', lib_dir, 'lib/'))
    include_files.extend(find_files('gschemas.compiled', base_prefix / 'share' / 'glib-2.0' / 'schemas/'))
    include_files.extend(find_files('pixbuf-loaders.cache', base_prefix / 'lib' / 'gdk-pixbuf-2.0' / '2.10.0'))

    for prefix in TYPELIB_PREFIXES:
        include_files.extend(find_files(f'{prefix}*.typelib', base_prefix / 'lib' / 'girepository-1.0'))

    build_dir = Path(argv[1], 'bin', 'rencher')
    if len(argv) > 2:
        dest_dir = Path(argv[2])
    else:
        dest_dir = Path(__file__).parent / 'build'
    icon_path = Path(__file__).parent / 'data' / 'assets' / 'rencher-icon.ico'
    # setup() requires the first argument to be 'build'
    sys.argv = [argv[0], 'build']

    # the script should look inside of venv even when outside of it (for ci)
    if (venv_path := Path('.venv')).is_dir():
        sys.path.insert(0, venv_path / 'Lib' / 'site-packages')

    setup(
        name='Rencher',
        description='Rencher',
        version=1,
        options={
            'build': {
                'build_base': dest_dir,
            },
            'build_exe': {
                'packages': ['requests', 'configparser', 'rarfile', 'cairo', 'rich'],
                'optimize': 2,
                'include_files': include_files,
                'include_msvcr': True,
            },
        },
        executables=[
            Executable(
                base='gui',
                script=build_dir,
                target_name='rencher',
                icon=icon_path,
                # copyright=rencher.__copyright__,
            ),
        ],
    )
    shutil.rmtree(tmp_dir)
    dir_name = f'exe.{sysconfig.get_platform()}-{sysconfig.get_python_version()}'
    print(f'Your frozen app is at "{dest_dir / dir_name}"')


def find_files(
    pattern: str,
    search_path: Path | str,
    dest_path: Path | str = Path(),
    recursive: bool = False,
) -> list[tuple[Path, Path]]:
    source_files: list[Path] = []
    files: list[tuple[Path, Path]] = []

    if isinstance(search_path, str):
        search_path = Path(search_path)
    if isinstance(dest_path, str):
        dest_path = Path(dest_path)

    if '*' in pattern:
        if recursive:
            source_files = list(search_path.rglob(pattern))
        else:
            source_files = list(search_path.glob(pattern))
    elif (source_file := Path(search_path / pattern)).is_file():
        source_files.append(source_file)
    else:
        return []

    for source_file in source_files:
        if dest_path == Path('.') and source_file.is_relative_to(base_prefix):
            target_file = source_file.relative_to(base_prefix)
            files.append((source_file, target_file))
        else:
            target_file = dest_path / source_file.relative_to(search_path)
            files.append((source_file, target_file))

    return files


if __name__ == '__main__':
    freeze(sys.argv)
