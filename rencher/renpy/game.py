import logging
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import override

from rencher.renpy.config import GameConfig
from rencher.renpy.paths import get_absolute_path, get_py_files, validate_game_files


class GameInvalidError(Exception):
    pass
class GameNoExecutableError(GameInvalidError):
    pass

class Game:
    rpath: Path
    apath: Path
    config: GameConfig


    def __init__(self, rpath: str | Path | None = None, apath: str | Path | None = None):
        rpath = Path(rpath) if rpath is not None else None
        apath = Path(apath) if apath is not None else None

        if not rpath and apath:
            self.rpath = apath
            self.apath = apath
        elif not apath and rpath:
            self.rpath = rpath
            if apath := get_absolute_path(rpath):
                self.apath = apath
            else:
                name = rpath.name
                raise GameInvalidError(f'{name} is not a valid game! ({rpath})')

        config_path = self.apath/'game'/'rencher.ini'
        self.config = GameConfig(config_path)

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Game):
            return self.rpath == other.rpath
        else:
            return False

    @override
    def __hash__(self):
        return hash(self.rpath)

    def validate(self) -> bool:
        """
            returns false if game cannot be run/isn't a real game
        """
        paths: list[str] = []
        for (topdir, dirs, files) in self.apath.walk():
            for dir in dirs:
                paths.append(str(topdir/dir))
            for file in files:
                paths.append(str(topdir/file))
        return validate_game_files(paths)

    def get_main_script(self) -> Path:
        """
            returns a path based off of the .py scripts located in apath
        """
        py_files = get_py_files(self.apath)
        codename = self.config.get_value('codename')

        if codename != '':
            return self.apath/f'{codename}.py'
        elif len(py_files) == 0:
            raise GameInvalidError(f'No executable found in {self.apath}')
        elif len(py_files) == 1:
            return py_files[0]
        else:  # more than 1, but with no codename assigned
            raise GameNoExecutableError

    def _lib_directories(self) -> tuple[str, ...]:
        arch = platform.machine()
        sys = platform.system().lower()
        if arch == 'AMD64':
            arch = 'x86_64'  # for windose

        return (
            f'py3-{sys}-{arch}',
            f'py2-{sys}-{arch}',
            f'{sys}-{arch}',
            f'{sys}-i686',  # last resort
        )

    def _exec_candidates(self):
        """
            yields exec paths in priority order:
                1. apath/codename.sh or codename.exe
                2. apath/lib/libdir/codename(.exe)
                3. apath/lib/libdir/pythonw(.exe)
        """
        is_windows = True if platform.system() == 'Windows' else False
        main_script = self.get_main_script()

        yield main_script.with_suffix('.exe' if is_windows else '.sh')

        for lib_dir in self._lib_directories():
            lib_path = self.apath/'lib'/lib_dir
            for name in (self.codename, 'pythonw'):
                yield (lib_path/name).with_suffix('.exe' if is_windows else '')

    def get_exec_path(self) -> Path | None:
        for canditate in self._exec_candidates():
            logging.debug(canditate)
            if canditate.is_file():
                logging.debug(f'its {canditate}')
                return canditate
        return None

    def get_renpy_version(self) -> list[int] | None:
        """
            tries to retrieve the game's ren'py version

            there a lot of ways that versions are tracked based on what version it is

            1. ren'py 6:
                * the version is located in `version_tuple` in `renpy/__init__.py`
                * the commit number is located in `vc_version` in `renpy/vc_version.py`

            2. ren'py 7:
                * the version is located in the first `version_tuple` located in `renpy/__init__.py`
                    - there are 2 version tuples
                    - the py2 one (the real one) and the py3 one (the one preparing for ren'py 8)[citation needed]
                * the commit number is located in `vc_version` in `renpy/vc_version.py`

            3. ren'py 7.6[citation needed]:
                * same as ren'py 7, however it's stored as a `VersionTuple`
                    - i have no idea if this occurs with other versions. i just noticed it in ren'py 7.6

            4. ren'py 8:
                * the version and commit number are located in `version` in `renpy/vc_version.py`

        Returns:
            the version as a string. returns `None` if it couldn't be determined
        """
        vc_path = self.apath/'renpy'/'vc_version.py'
        init_path = self.apath/'renpy'/'__init__.py'
        commit: int | None = None
        version: list[int] = []

        if vc_path.is_file():
            with open(vc_path) as f:
                vc_content = f.read()
                version_match = re.findall(r'version .*\'(.*)\'', vc_content, re.MULTILINE)
                if version_match:
                    version = list(map(int, version_match[0].split('.')))
                commit_match = re.findall(r'vc_version.*(\b\d+\b)', vc_content, re.MULTILINE)
                if commit_match:
                    commit = int(commit_match[0])

        if init_path.is_file():
            with open(init_path) as f:
                init_content = f.read()
                version_match = re.findall(r'version_tuple.*\((\d.*)\)', init_content, re.MULTILINE)
                if version_match:
                    version_list = re.findall(r'\b\d+\b', version_match[0])
                    version = list(map(int, version_list[0].split('.')))

        if commit:
            version.append(commit)
        return version

    def run(self) -> subprocess.Popen[bytes]:
        """
            launches the game with the specified options
        """
        self.setup()
        self.config.read()  # just to be SURE

        args: list[str] = [str(self.get_exec_path())]
        if args[0] == '':
            ...
        env: dict[str, str] = {}

        if self.config['overwritten']['skip_splash_scr'] == 'true':
            env['RENPY_SKIP_SPLASHSCREEN'] = '1'
        elif env.get('RENPY_SKIP_SPLASHSCREEN'):
            env.pop('RENPY_SKIP_SPLASHSCREEN')
        if self.config['overwritten']['skip_main_menu'] == 'true':
            env['RENPY_SKIP_MAIN_MENU'] = ('Did you know you can put anything here and it stills work '
                                           'like ren\'py doesn\'t even check for the value it\'s crazy')
        elif env.get('RENPY_SKIP_MAIN_MENU'):
            env.pop('RENPY_SKIP_MAIN_MENU')

        # py_path = str(self.get_main_script())
        # librenpython_path = os.path.join(os.path.dirname(args[0]), 'librenpython.so')
        # if os.path.isfile(librenpython_path):
        #     args.extend([py_path])
        # else:
        #     args.extend(['-EO', py_path])

        if self.config['overwritten']['forced_save_dir'] == 'true':
            save_dir = os.path.join(self.apath, 'game', 'saves')

            # save_slot = self.config['options'].getint('save_slot')
            # if 1 < save_slot <= 10:
            #     save_dir = os.path.join(save_dir, str(save_slot))
            #     logging.debug(save_dir)

            args.extend(['--savedir', save_dir])

        if os.environ.get('FLATPAK_ID'):
            args.insert(0, 'flatpak-spawn')
            args.insert(1, '--host')
            # flatpak ignores the env parameter in Popen()
            for key, value in env.items():
                args.insert(2, f'--env={key}={value}')

        config_dict = {}
        for item in self.config['overwritten']:
            config_dict[item] = self.config['overwritten'][item]
        logging.info(f'Running "{os.path.basename(self.rpath)}"...')
        logging.debug(f'"{os.path.basename(self.rpath)}" config: {config_dict}')
        logging.debug(f'"{os.path.basename(self.rpath)}" args: {args}')
        return subprocess.Popen(args, env=os.environ | env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # def run_wine()

    def setup(self) -> None:
        """
            1. makes files executable for linux

            2. in newer ren'py versions, a dll called "librenpython" got added
            this library includes all the python libraries ren'py needs (i think)
            this makes modding a bit more complicated, as certain conflicts might arise

            PRE LIBRENPYTHON:
            * libraries were located in lib/ inside the exec path
            * you need to pass "-EO <python_path>" to args

            POST LIBRENPYTHON:
            * lib/ folder is gone and instead replaced by librenpython
            * you need to pass "<python_path>" to args instead
        """

        if platform.system() != 'Linux':
            return

        logging.debug('Doing setup...')

        for candidate in self._exec_candidates():
            if not candidate.is_file():
                continue
            mode = os.stat(candidate).st_mode
            os.chmod(candidate, mode | 0o111)

            if candidate.parent == self.apath:
                # we're not in lib. where we want to actually do stuff
                continue

            libs_path = candidate.parent/'libs'
            librenpython_path = candidate.parent/'librenpython.so'
            if libs_path.is_dir() and librenpython_path.is_file():
                shutil.rmtree(libs_path)
                logging.debug(f'Patched {candidate.parent.name}!')

    def cleanup(self, playtime: float) -> None:
        self.config.read()
        self.config['info']['playtime'] = str(playtime)
        self.config['info']['last_played'] = str(int(time.time()))
        self.config.write()

    @property
    def name(self) -> str:
        nickname = self.config.get_value('nickname')
        if isinstance(nickname, str):
            return nickname
        else:
            return self.rpath.name
    @property
    def codename(self) -> str:
        return self.get_main_script().stem
    @property
    def version(self) -> list[int] | None:
        return self.get_renpy_version()
    @property
    def is_mod(self):
        py_files = get_py_files(self.apath)
        if len(py_files) > 1:
            return True
        elif len(py_files) <= 1:
            return False
        else:
            raise FileNotFoundError(f'{self.rpath.name} has no .py files!')
    @property
    def is_valid(self):
        return self.validate()
    @property
    def is_launchable(self) -> bool:
        if self.get_main_script():
            return True
        else:
            return False
