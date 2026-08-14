import os
import platform
from functools import lru_cache
from pathlib import Path

local_path = Path()
config_path = Path()

if platform.system() == 'Linux':
    # TODO figure out why this isn't in .var/
    data_home = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    local_path = data_home / 'rencher'
    config_path = local_path / 'config.ini'
elif platform.system() == 'Windows':
    local_path = Path.home() / 'AppData' / 'Local' / 'Rencher'
    config_path = local_path / 'config.ini'

@lru_cache
def get_py_files(apath: Path | str) -> list[Path]:
    if isinstance(apath, str):
        apath = Path(apath)

    # return [file.name for file in apath.iterdir() if file.suffix == '.py']
    return [file for file in apath.iterdir() if file.suffix == '.py']

@lru_cache
def get_rpa_files(rpath: Path | str) -> list[Path]:
    if isinstance(rpath, str):
        rpath = Path(rpath)

    rp_files: list[Path] = []
    for top_dir, _, files in rpath.walk():
        for f in files:
            ext = os.path.splitext(f)[1]
            if not ext.startswith('.rp'):
                continue
            # generic engine file
            if f.startswith('00'):
                continue
            # .rpym files can be compiled (.rypmc)
            if ext.startswith('.rpym'):
                continue
            # cache file
            if ext == '.rpyb':
                continue
            rp_files.append(top_dir / f)

    return rp_files

def get_rpa_path(rpath: Path | str) -> Path | None:
    if isinstance(rpath, str):
        rpath = Path(rpath)

    game_files = get_rpa_files(rpath)
    if not game_files:
        return None

    # some mods apparently store ren'py files in lib/
    # those are further nested inside the game so just try and get the top folder
    rpa_path = min(game_files, key=lambda path: len(path.parents))
    return rpa_path.parent

def get_absolute_path(rpath: Path | str) -> Path | None:
    if isinstance(rpath, str):
        rpath = Path(rpath)

    rpa_path = get_rpa_path(rpath)
    if rpa_path:
        return rpa_path.parent
    return None

def validate_game_files(files: list[str]) -> bool:
    """
    a quick validation function, to be used before importing games

    it checks for game files, the 3 required folders, a python script and engine files

    Args:
        files: the list of files
    Returns:
        true if it's a valid game, false if it's not
    """
    if not files:
        return False

    rp_files = [file for file in files if '.rp' in os.path.splitext(file)[1]]
    game_files = [
        rp_file for rp_file in rp_files
        if os.path.basename(rp_file)[0:2] != '00'  # generic engine file
        if '.rpym' not in os.path.splitext(rp_file)[1]  # .rpym files can be compiled (.rypmc)
        if os.path.splitext(rp_file)[1] != '.rpyb'  # cache file
    ]
    if not game_files:
        return False

    rpa_path = min(game_files, key=lambda path: len(path.split(os.sep)))
    apath = os.path.abspath(os.path.join(rpa_path, '..', '..'))
    rel_files = [os.path.relpath(file, apath) for file in files]

    required_folders = [file for file in rel_files
                        if len(file.split(os.sep)) == 1
                        if file in ['game', 'lib', 'renpy']]
    if len(required_folders) != 3:
        return False

    game_scripts = [file for file in rel_files
                    if len(file.split(os.sep)) == 1
                    if os.path.splitext(file)[1] == '.py']
    if not game_scripts:
        return False

    game_files = [file for file in rel_files
                  if os.path.commonpath(['game', file])
                  if os.path.splitext(file)[1] == '.rpa']
    if not game_files:
        return False

    engine_files = [file for file in rel_files
                    if os.path.commonpath(['renpy', file])
                    if os.path.splitext(file)[1] in ['.py', '.pyo', '.pyx', '.rpym', '.rpymc']]
    if not engine_files:
        return False

    return True
