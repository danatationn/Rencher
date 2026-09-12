import logging
import os
import platform
import shutil
import threading
import time
import uuid
import zipfile
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING, override

import rarfile
from gi.repository import GLib, GObject

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.utils import windowficate_path
from rencher.renpy.config import RencherConfig
from rencher.renpy.game import Game
from rencher.renpy.paths import get_absolute_path, get_py_files, get_rpa_files, get_rpa_path, validate_game_files


class RencherTask(GObject.Object):
    """
    Overridable class to simplify background tasks

    The main overridable classes are __init__(), and run()

    DO NOT do any heavy work in __init__(), as it will block the main GTK thread
    """

    __gtype_name__: str = 'RencherTask'
    __gsignals__: dict[str, tuple[GObject.SignalFlags, None, tuple[object]]] = {
        'message': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    if TYPE_CHECKING:
        label: str
        progress: int
        max_progress: int
        finished: bool
    else:
        label = GObject.Property(type=str)
        progress = GObject.Property(type=int)
        max_progress = GObject.Property(type=int)
        finished = GObject.Property(type=bool, default=False)

    _uuid: uuid.UUID
    _thread: threading.Thread | None
    _cancel_flag: threading.Event

    def __init__(self, label: str, max_progress: int = -1):
        super().__init__()
        self.label = label
        self.max_progress = max_progress
        self.progress = 0
        self._uuid = uuid.uuid4()
        self._thread = None
        self._cancel_flag = threading.Event()
        self.finished = False

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_wrapper, daemon=True)
        self._thread.start()

    def _run_wrapper(self) -> None:
        try:
            logging.debug(f'Starting task {self.uuid} - "{self.label}"')
            self.run()
        except Exception as e:
            logging.error(f'Task {self.uuid} - "{self.label}" has failed: {e}')
            # GLib.idle_add(self.set_property, 'error', str(e))
        finally:
            GLib.idle_add(self.set_property, 'finished', True)

    def run(self) -> None:
        """OVERRIDE THIS! Also don't call directly . run w/ self.start()"""
        raise NotImplementedError

    def cancel(self) -> None:
        self._cancel_flag.set()

    def advance(self, amount: int = 1) -> None:
        def _update():
            self.progress += amount
            self.notify('fraction')
            return False
        GLib.idle_add(_update)

    def message(self, text: str) -> None:
        """Sends a toast to the window. It goes through library which is hooked by the window"""
        logging.info(text)
        GLib.idle_add(self.emit, 'message', text)

    @GObject.Property(type=float)
    def fraction(self) -> float:
        if self.max_progress <= 0:
            return 0.0  # TODO think about this behavior
        return min(self.progress/self.max_progress, 1.0)

    @property
    def is_cancelled(self):
        return self._cancel_flag.is_set()
    @property
    def uuid(self):
        return self._uuid

class DeleteGameTask(RencherTask):
    rpath: Path

    def __init__(self, rpath: Path | str):
        super().__init__(str(rpath))
        self.rpath = Path(rpath)

    @override
    def run(self) -> None:
        paths_to_delete: list[tuple[Path, bool]] = []  # `True` if directory, `False` if file

        for root, dirs, files in self.rpath.walk(top_down=False):
            if self.is_cancelled:
                return

            for filename in files:
                paths_to_delete.append((root/filename, False))
            for dirname in dirs:
                paths_to_delete.append((root/dirname, True))

        paths_to_delete.append((self.rpath, True))

        GLib.idle_add(self.set_property, 'max_progress', len(paths_to_delete))

        for path, is_dir in paths_to_delete:
            if self.is_cancelled:
                return

            try:
                if is_dir:
                    path.rmdir()
                else:
                    path.unlink(missing_ok=True)
            except (PermissionError, FileNotFoundError, OSError) as e:
                logging.warning(f'Failed to delete {path}: {e}')

            self.advance()

        self.message(_('"{}" has been deleted').format(self.rpath.name))

class NukeGamesTask(RencherTask):
    """deletes ALL games from the specified data directory"""

    data_dir: Path

    @override
    def __init__(self, data_dir: Path | str | None = None):
        if not data_dir:
            data_dir = RencherConfig().get_data_dir()
        self.data_dir = Path(data_dir)

        label = _('Deleting all games from "{}"').format(data_dir)
        super().__init__(label)

    ...

class ImportGameTask(RencherTask):
    source_path: Path
    nickname: str | None
    target_entry: GameEntry | None
    game_path: Path | None  # is some by the end
    game: Game | None

    def __init__(self, source_path: Path, nickname: str | None = None, target_entry: GameEntry | None = None):
        label = nickname if nickname else source_path.name
        super().__init__(label)
        self.source_path = source_path
        self.nickname = nickname
        self.target_entry = target_entry
        self.game_path = None
        self.game = None

    @override
    def run(self) -> None:
        config = RencherConfig()
        data_dir = Path(config.get_data_dir())
        archive: zipfile.ZipFile | rarfile.RarFile | None = None
        folder_file_list: list[Path] = [] # all the files in the archive/folder
        archive_file_list: list[str] = []
        start_time: float = time.perf_counter()  # to count how long it took to import
        name = self.nickname or self.source_path.stem
        game_path: Path | None

        """
        Seeing if it's an archive or a folder then getting a list of all the files
        """
        if self.source_path.is_file():
            try:
                if self.source_path.suffix == '.zip':
                    logging.debug(f'Zip file detected ("{self.source_path}")')
                    archive = zipfile.ZipFile(self.source_path)
                elif self.source_path.suffix == '.rar':  # .rar
                    logging.debug(f'Rar file detected ("{self.source_path}")')
                    archive = rarfile.RarFile(self.source_path)
                else:
                    logging.error(f'Unknown file type detected ("{self.source_path}")')
                    self.message(_('The archive format is not supported!'))
                    return
            except (rarfile.BadRarFile, rarfile.NotRarFile, zipfile.BadZipFile):
                self.message(_('The archive supplied is invalid!'))
                return
            else:
                archive_file_list = archive.namelist()
        elif self.source_path.is_dir():
            logging.debug(f'Folder detected ("{self.source_path}/")')
            folder_file_list = list(self.source_path.rglob('*'))
        else:
            return

        if not self.target_entry and not validate_game_files(archive_file_list or folder_file_list):
            self.message(_('The game supplied is invalid!'))
            return

        """
        Determining a unique directory name
        """
        folder_count = 2
        game_path = None
        dir_time = time.perf_counter()
        while game_path is None or not os.path.exists(game_path):
            if time.perf_counter() - dir_time > 1:
                # this will never happen unless you're a freak
                self.message(_('Couldn\'t come up with a name!'))
                return

            # in case nickname is not set, use the path stem
            possible_paths: list[Path] = [
                data_dir / 'games' / name,
                data_dir / 'games' / self.source_path.stem,
                data_dir / 'games' / f'{name} ({folder_count})',
                data_dir / 'games' / f'{self.source_path.stem} ({folder_count})',
            ]
            folder_count += 1

            for path in possible_paths:
                if config.get('settings', 'windowficate_filenames') == 'true' or platform.system() == 'Windows':
                    new_path = windowficate_path(path)
                else:
                    new_path = path
                if not new_path.exists():
                    new_path.mkdir(parents=True, exist_ok=True)
                    game_path = new_path
                    break

        if not self.is_cancelled:
            logging.info(_(f'Importing the game at "{game_path}/"'))
            self.game_path = game_path

        if self.target_entry:
            game_files = self.target_entry.game.rpath.rglob('*')
            total_files = len(folder_file_list or archive_file_list) + len(list(game_files))
        else:
            total_files = len(folder_file_list or archive_file_list)

        GLib.idle_add(self.set_property, 'max_progress', total_files)

        """
        Copy files from the source to the game directory
        """
        def should_skip(path: Path | str) -> bool:
            path = Path(path)
            if path.name == 'rencher.ini' and path.parent.name == 'game':
                return True
            if path.name == 'persistent':
                return True
            if path.suffix == '.save':
                return True

            return False

        for path in archive_file_list:
            if self.is_cancelled or not archive:
                break

            if should_skip(path):
                continue

            archive.extract(path, game_path)  # pyright: ignore[reportUnknownMemberType]
            self.advance()

        for path in folder_file_list:
            if self.is_cancelled:
                break

            if should_skip(path):
                continue

            relative_path = path.relative_to(self.source_path)
            target_path = game_path / relative_path

            if path.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
            else:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                path.copy(target_path)

            self.advance()

        """
        Some R6 mods come with .rpa files in root and nothing else
        This tries to make a game/ directory and move them there
        """
        if self.target_entry:
            rpa_path = get_rpa_path(game_path)
            apath = get_absolute_path(game_path)
            if not rpa_path or not apath:
                self.message(_('No game files found; target game is corrupt'))
                return
            if rpa_path == apath:
                new_rpa_path = apath / 'game'
                rpa_files = get_rpa_files(apath)
                if not new_rpa_path.exists():
                    new_rpa_path.mkdir(parents=True, exist_ok=True)
                for path in rpa_files:
                    if self.is_cancelled:
                        break
                    relative_path = path.relative_to(rpa_path)
                    target_path = new_rpa_path / relative_path
                    path.move(target_path)

                # get_absolute_path is based off of get_rpa_files so we need to clear the cache
                # otherwise it will dump the game files outside the folder
                get_rpa_files.cache_clear()

            apath = get_absolute_path(game_path)
            if not apath:
                ...
                return

            for path in self.target_entry.game.apath.rglob('*'):
                if self.is_cancelled:
                    break

                relative_path = path.relative_to(self.target_entry.game.apath)
                target_path = apath / relative_path

                if target_path.exists():
                    continue
                if should_skip(path):
                    continue
                if path.is_dir():
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    path.copy(target_path)

                self.advance()

        if not self.is_cancelled:
            game = Game(rpath=game_path)
            self.game = game
            if self.nickname:
                game.config.set('info', 'nickname', self.nickname)
            game.config.set('info', 'added_on', str(time.time()))
            game_scripts = get_py_files(game.apath)
            if len(game_scripts) == 2 and self.target_entry:
                try:
                    game_codenames = [script.stem for script in game_scripts]
                    game_codenames.remove(self.target_entry.codename)
                    game.config.set('info', 'codename', game_codenames[0])
                except ValueError:
                    logging.warning(_('Couldn\'t determine codename'))
                    pass
            game.config.write()

            # self.window.library.add_game(game_path)  ?
            # selected_row = self.window.library_list_box.get_selected_row()
            # if not selected_row:
            #     result = self.window.library.find(game_path)
            #     if result:
            #         _, game_item = result
            #         row = self.window.rows[game_item]
            #         self.window.library_list_box.select_row(row)

            logging.info(f'Importing done in {time.perf_counter() - start_time:.2f}s')
            if config.get('settings', 'delete_on_import') == 'true':
                try:
                    # if archive is still open windows will whine and scream and not let you
                    if archive:
                        archive.close()
                    self.source_path.unlink()
                except PermissionError:
                    logging.error(_('Couldn\'t delete archive! File left untouched'))
                except Exception as e:
                    logging.error(f"Couldn't delete archive! {e}")
                else:
                    logging.info(f'Archive "{self.source_path.name}" deleted!')

        else:
            shutil.rmtree(game_path)
            logging.info(f'Importing cancelled. Total thread runtime: {time.perf_counter() - start_time:.2f}s')
