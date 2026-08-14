import glob
import logging
import os
import shutil
import threading
import time
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, override

import rarfile
from gi.repository import Adw, Gio, GLib, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.utils import windowficate_path
from rencher.renpy.config import RencherConfig
from rencher.renpy.game import Game
from rencher.renpy.paths import (
    get_absolute_path,
    get_py_files,
    get_rpa_files,
    get_rpa_path,
    validate_game_files,
)

if TYPE_CHECKING:
    from rencher.gtk.window import MainWindow


@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/import.ui')
class ImportDialog(Adw.Dialog):
    __gtype_name__: str = 'ImportDialog'

    title_entry: Adw.EntryRow = Gtk.Template.Child()
    location_entry: Adw.EntryRow = Gtk.Template.Child()
    location_picker: Gtk.Button = Gtk.Template.Child()
    type_combo: Adw.ComboRow = Gtk.Template.Child()
    game_combo: Adw.ComboRow = Gtk.Template.Child()
    import_button: Adw.ActionRow = Gtk.Template.Child()
    # mod_switch: Adw.SwitchRow = Gtk.Template.Child()

    window: 'MainWindow'
    thread: threading.Thread
    cancel_flag: threading.Event
    has_imported: bool = False

    selected_type: str = 'Archive (.zip, .rar)'
    archive_location: str = ''
    folder_location: str = ''

    def __init__(self, window: 'MainWindow', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.window = window
        self.do_show()

        string_list = Gtk.StringList()
        string_list.append('Archive (.zip, .rar)')
        string_list.append('Folder')
        self.type_combo.set_model(string_list)


    @override
    def do_show(self):
        list_store = Gio.ListStore.new(GameEntry)
        list_store_len = 0

        list_store.append(GameEntry())  # option for no mod . default
        for _, game_item in enumerate(self.window.library.store):
            if not isinstance(game_item, GameEntry):
                continue
            if not game_item.game.is_mod:
                list_store.append(game_item)
                list_store_len += 1

        def _name_for_entry(entry: GameEntry, *_args):
            if list_store_len == 0:
                return 'None'
            elif hasattr(entry, 'game'):
                return os.path.basename(entry.rpath)
            else:
                return 'N/A'

        self.game_combo.set_model(list_store)
        self.game_combo.set_expression(
            Gtk.ClosureExpression.new(str, _name_for_entry, None),
        )

        if self.has_imported:
            self.title_entry.set_text('')
            self.location_entry.set_text('')
            # self.mod_switch.set_active(False)
            self.has_imported = False

    @Gtk.Template.Callback()
    def on_type_changed(self, *_):
        selected_item = self.type_combo.get_selected_item()
        assert isinstance(selected_item, Gtk.StringObject)
        self.selected_type = selected_item.get_string()
        if self.selected_type == 'Folder':
            self.location_entry.set_title('Folder Location')
            self.location_picker.set_icon_name('folder-open-symbolic')
            self.location_entry.set_text(self.folder_location)
        else:
            self.location_entry.set_title('Archive Location')
            self.location_picker.set_icon_name('file-cabinet-symbolic')
            self.location_entry.set_text(self.archive_location)

    @Gtk.Template.Callback()
    def on_location_changed(self, entry_row: Adw.EntryRow):
        location_text = entry_row.get_text()
        if self.selected_type == 'Folder':
            self.folder_location = location_text
        else:
            self.archive_location = location_text

        try:
            if Path(location_text).suffix == '.zip':
                zipfile.ZipFile(location_text)
            if Path(location_text).suffix == '.rar':
                rarfile.RarFile(location_text)
        except (rarfile.BadRarFile, rarfile.NotRarFile, zipfile.BadZipFile, FileNotFoundError):
            self.import_button.set_sensitive(False)
        else:
            self.import_button.set_sensitive(True)
            if not self.title_entry.get_text():
                if Path(location_text).is_file():
                    name = Path(location_text).stem
                else:
                    name = Path(location_text).name
                self.title_entry.set_text(name)

    @Gtk.Template.Callback()
    def on_picker_clicked(self, _) -> None:
        dialog = Gtk.FileDialog()
        if self.selected_type == 'Folder':
            dialog.select_folder(self.window, None, self.on_file_selected)
        else:
            dialog.open(self.window, None, self.on_file_selected)

    def on_file_selected(self, dialog: Gtk.FileDialog, result):
        try:
            if self.selected_type == 'Folder':
                file = dialog.select_folder_finish(result)
            else:
                file = dialog.open_finish(result)
            path = file.get_path()
            self.location_entry.set_text(path if path else '')
        except GLib.Error:
            pass  # dialog was dismissed by user

    @Gtk.Template.Callback()
    def on_import_clicked(self, _) -> None:
        self.cancel_flag = threading.Event()
        self.has_imported = True
        self.thread = threading.Thread(target=self.import_game)
        self.thread.start()
        self.close()

    def import_game(self):
        name = self.title_entry.get_text()
        location = self.location_entry.get_text()
        location_stem = os.path.splitext(os.path.basename(location))[0]
        archive: zipfile.ZipFile | rarfile.RarFile | None
        modded_game = self.game_combo.get_selected_item()
        is_mod = hasattr(modded_game, '_game')
        if not modded_game:
            # TODO throw error
            ...
            return

        data_dir = RencherConfig().get_data_dir()
        game_dir = os.path.join(data_dir, 'games')

        if not os.path.exists(location):
            return

        suffix = os.path.splitext(location)[1]
        if suffix in ['.zip', '.rar']:
            logging.debug(f'Archive detected ("{location})"')
            try:
                if suffix == '.zip':
                    archive = zipfile.ZipFile(location)
                else:
                    archive = rarfile.RarFile(location)
            except (rarfile.BadRarFile, rarfile.NotRarFile, zipfile.BadZipFile):
                self.window.toast_overlay.add_toast(
                    Adw.Toast(
                        title='The archive supplied is invalid!',
                        timeout=5,
                    ),
                )
                return
            else:
                files = archive.namelist()

        elif os.path.isdir(location):
            logging.debug(f'Folder detected ("{location}/")')
            files = glob.glob(f'{location}/**/*', recursive=True)
        else:
            return

        if not is_mod and not validate_game_files(files):
            self.window.toast_overlay.add_toast(
                Adw.Toast(
                    title='The game supplied is invalid!',
                    timeout=5,
                ),
            )
            return

        count = 2
        start = time.perf_counter()
        rpath = None
        config = RencherConfig()
        while rpath is None or not os.path.exists(rpath):
            if time.perf_counter() - start > 1:
                # this will never happen unless you're a freak
                self.window.toast_overlay.add_toast(
                    Adw.Toast(
                        title="Couldn't come up with a name!",
                        timeout=5,
                    ),
                )
                return

            possible_paths = [
                os.path.join(game_dir, location_stem),
                os.path.join(game_dir, name),
                os.path.join(game_dir, f'{location_stem} ({count})'),
                os.path.join(game_dir, f'{name} ({count})'),
            ]
            for path in possible_paths:
                if config.get('settings', 'windowficate_filenames', fallback=None) == 'true':
                    new_path = windowficate_path(path)
                else:
                    new_path = path
                if not os.path.exists(new_path):
                    os.makedirs(new_path, exist_ok=True)
                    rpath = new_path
                    break

            count += 1

        if not self.cancel_flag.is_set():
            logging.info(f'Importing the game at "{rpath}/"')
        start = time.perf_counter()

        if is_mod:
            game_files = glob.glob(f'{modded_game.rpath}/**', recursive=True)
            total_work = len(files) + len(game_files)
        else:
            total_work = len(files)

        # task = self.window.tasks_popover.new_task(name, TaskTypeEnum.IMPORT, self.cancel_flag, total_work)

        for i, path in enumerate(files):
            if self.cancel_flag.is_set():
                break
            if archive:
                archive.extract(path, rpath)
            else:
                relative_path = os.path.relpath(path, location)
                target_path = os.path.join(rpath, relative_path)

                if os.path.isdir(path):
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy(path, target_path)

            # self.window.tasks_popover.update_task(task, i)

        if is_mod:
            rpa_path = get_rpa_path(rpath)
            apath = get_absolute_path(rpath)
            if os.path.dirname(rpa_path) == apath:
                new_rpa_path = os.path.join(apath, 'game')
                rpa_files = get_rpa_files(apath)
                if not os.path.exists(new_rpa_path):
                    os.makedirs(new_rpa_path, exist_ok=True)
                for path in rpa_files:
                    if self.cancel_flag.is_set():
                        break
                    relative_path = os.path.relpath(path, rpa_path)
                    target_path = os.path.join(new_rpa_path, relative_path)
                    shutil.move(path, target_path)

                # get_absolute_path is based off of get_rpa_files so we need to clear the cache
                # otherwise it will dump the game files outside the folder
                get_rpa_files.cache_clear()

            apath = get_absolute_path(rpath)

            for i, path in enumerate(glob.iglob(f'{modded_game.apath}/**', recursive=True)):
                if self.cancel_flag.is_set():
                    break

                relative_path = os.path.relpath(path, modded_game.apath)
                target_path = os.path.join(apath, relative_path)

                if os.path.exists(target_path):
                    continue
                if os.path.basename(target_path) == 'rencher.ini':
                    continue
                if os.path.basename(target_path) == 'persistent':
                    continue
                if os.path.splitext(target_path)[1] == '.save':
                    continue
                if os.path.isdir(path):
                    os.makedirs(target_path, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy(path, target_path)

                # self.window.tasks_popover.update_task(task, len(files) + i)

        if not self.cancel_flag.is_set():
            game = Game(rpath=rpath)
            game.config.set('info', 'nickname', name)
            game.config.set('info', 'added_on', str(time.time()))
            game_scripts = get_py_files(game.apath)
            if len(game_scripts) == 2 and is_mod:
                try:
                    # ugh
                    game_codenames = [os.path.splitext(os.path.basename(codename))[0] for codename in game_scripts]
                    game_codenames.remove(modded_game.codename)
                    game.config.set('info', 'codename', game_codenames[0])
                except ValueError:
                    logging.warn("Couldn't determine codename")
                    pass
            game.config.write()

            self.window.library.add_game(rpath)
            selected_row = self.window.library_list_box.get_selected_row()
            if not selected_row:
                result = self.window.library.find(rpath)
                if result:
                    _, game_item = result
                    row = self.window.rows[game_item]
                    self.window.library_list_box.select_row(row)

            logging.info(f'Importing done in {time.perf_counter() - start:.2f}s')
            if RencherConfig()['settings']['delete_on_import'] == 'true':
                try:
                    # if archive is still open windows will whine and scream and not let you
                    if archive:
                        archive.close()
                    os.unlink(location)
                except PermissionError:
                    logging.error("Couldn't delete archive! File left untouched")
                except Exception as e:
                    logging.error(f"Couldn't delete archive! {e}")
                else:
                    logging.info(f'Archive "{location_stem}" deleted!')

        else:
            shutil.rmtree(rpath)
            logging.info(f'Importing cancelled. Total thread runtime: {time.perf_counter() - start:.2f}s')
        # self.window.tasks_popover.update_task(task, total_work)
