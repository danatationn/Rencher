import os
import threading
import zipfile
from enum import Enum
from gettext import gettext as _
from pathlib import Path
from typing import TYPE_CHECKING, override

import rarfile
from gi.repository import Adw, Gio, GLib, Gtk
from gi.repository.GObject import GParamSpec

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.utils import gtk_template_callback, gtk_template_child

if TYPE_CHECKING:
    from rencher.gtk.window import MainWindow


class ImportTypeEnum(Enum):
    ARCHIVE = 0
    FOLDER = 1

@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/import.ui')
class ImportDialog(Adw.Dialog):
    __gtype_name__: str = 'ImportDialog'

    title_entry: Adw.EntryRow = gtk_template_child()
    location_entry: Adw.EntryRow = gtk_template_child()
    location_picker: Gtk.Button = gtk_template_child()
    type_combo: Adw.ActionRow = gtk_template_child()
    game_combo: Adw.ComboRow = gtk_template_child()
    import_button: Adw.ActionRow = gtk_template_child()
    validation_banner: Adw.Banner = gtk_template_child()

    window: 'MainWindow'
    thread: threading.Thread
    cancel_flag: threading.Event
    has_imported: bool

    selected_type: ImportTypeEnum
    archive_location: str
    folder_location: str

    def __init__(self, window: 'MainWindow', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.selected_type = ImportTypeEnum.ARCHIVE
        self.archive_location = ''
        self.folder_location = ''
        self.has_imported = False
        self.window = window

        # after importing something, focus will be lost from title_entry
        self.connect('map', lambda *_: self.title_entry.grab_focus())

    @override
    def do_show(self):
        list_store = Gio.ListStore.new(GameEntry)
        list_store_len = 0

        list_store.append(GameEntry())  # option for no mod . default
        for game_item in self.window.library.store:
            if not isinstance(game_item, GameEntry):
                continue
            if not game_item.game.is_mod:
                list_store.append(game_item)
                list_store_len += 1

        def _name_for_entry(entry: GameEntry, *_args: None):
            if hasattr(entry, 'game'):
                return os.path.basename(entry.rpath)
            else:
                return ''

        self.game_combo.set_model(list_store)
        self.game_combo.set_expression(
            Gtk.ClosureExpression.new(str, _name_for_entry, None),
        )

    @override
    def do_closed(self) -> None:
        if self.has_imported:
            self.title_entry.set_text('')
            self.location_entry.set_text('')
            self.archive_location = ''
            self.folder_location = ''
            self.has_imported = False

    @gtk_template_callback
    def on_type_changed(self, toggle_group: Adw.ToggleGroup, _uint: GParamSpec):
        active = ImportTypeEnum(toggle_group.get_active())
        self.selected_type = active

        if active == ImportTypeEnum.FOLDER:
            self.location_entry.set_title(_('Folder Location'))
            self.location_picker.set_icon_name('folder-open-symbolic')
            self.location_entry.set_text(self.folder_location)
        elif active == ImportTypeEnum.ARCHIVE:
            self.location_entry.set_title(_('Archive Location'))
            self.location_picker.set_icon_name('file-cabinet-symbolic')
            self.location_entry.set_text(self.archive_location)

    def _fail(self, message: str) -> None:
        self.import_button.set_sensitive(False)
        self.validation_banner.set_revealed(True)
        self.validation_banner.set_title(message)

    @gtk_template_callback
    def on_location_changed(self, entry_row: Adw.EntryRow):
        location_text = entry_row.get_text()
        path = Path(location_text)

        if self.selected_type == ImportTypeEnum.FOLDER:
            self.folder_location = location_text
        elif self.selected_type == ImportTypeEnum.ARCHIVE:
            self.archive_location = location_text

        if location_text == '':
            self.import_button.set_sensitive(False)
            return

        if not Path(path).exists():
            self._fail(_('The path does not exist'))
            return

        if self.selected_type == ImportTypeEnum.ARCHIVE:
            if path.suffix not in ['.zip', '.rar']:
                self._fail(_('The archive needs to be .zip or .rar'))
                return

            is_valid_archive = (
                path.suffix == '.zip' and zipfile.is_zipfile(path)
            ) or (
                path.suffix == '.rar' and rarfile.is_rarfile(path)  # pyright: ignore[reportUnknownMemberType]
            )

            if not is_valid_archive:
                self._fail(_('The archive is corrupt'))
                return

        self.validation_banner.set_revealed(False)
        self.import_button.set_sensitive(True)
        if not self.title_entry.get_text():
            if self.selected_type == ImportTypeEnum.ARCHIVE:
                name = path.stem
            else:
                name = path.name
            self.title_entry.set_text(name)

    @gtk_template_callback
    def on_picker_clicked(self, _) -> None:
        dialog = Gtk.FileDialog()
        if self.selected_type == ImportTypeEnum.FOLDER:
            dialog.select_folder(self.window, None, self.on_file_selected)
        elif self.selected_type == ImportTypeEnum.ARCHIVE:
            dialog.open(self.window, None, self.on_file_selected)

    def on_file_selected(self, dialog: Gtk.FileDialog, result: Gio.Task):
        try:
            if self.selected_type == ImportTypeEnum.FOLDER:
                file = dialog.select_folder_finish(result)
            else:
                file = dialog.open_finish(result)
            path = file.get_path()
            self.location_entry.set_text(path if path else '')
        except GLib.Error:
            pass  # dialog was dismissed by user

    @gtk_template_callback
    def on_import_clicked(self, _button: Adw.ActionRow) -> None:
        target_game = self.game_combo.get_selected_item()
        game_rpath = ''
        if hasattr(target_game, '_game') and isinstance(target_game, GameEntry):
            game_rpath = target_game.rpath

        self.activate_action(
            'library.import-game',
            GLib.Variant('(sss)', (self.location_entry.get_text(), self.title_entry.get_text(), game_rpath)),
        )

        self.has_imported = True
        self.close()
