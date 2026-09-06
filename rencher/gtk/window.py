from enum import Enum
import logging
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.library import Library
from rencher.gtk.tasks import ImportGameTask, RencherTask
from rencher.gtk.utils import gtk_template_callback, gtk_template_child
from rencher.gtk.widgets.codename_dialog import RencherCodename
from rencher.gtk.widgets.game_detail_view import GameDetailView
from rencher.gtk.widgets.game_row import GameRow
from rencher.gtk.widgets.import_dialog import ImportDialog
from rencher.gtk.widgets.settings_dialog import SettingsDialog

if TYPE_CHECKING:
    from rencher.gtk.application import MainApplication

class SortComboEnum(Enum):
    NAME = 0
    LAST_PLAYED = 1
    PLAYTIME = 2
    ADDED_ON = 3

@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/window.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__: str = 'MainWindow'

    # variables
    rows: dict[GameEntry, GameRow]
    games: dict[GameRow, GameEntry]
    game_views: dict[GameEntry, GameDetailView]
    task_rows: dict[RencherTask, GameRow]

    filter_text: str = ''
    combo_index: SortComboEnum = SortComboEnum.NAME
    ascending_order: bool

    # classes
    app: MainApplication
    settings_dialog: SettingsDialog
    import_dialog: ImportDialog
    codename_dialog: RencherCodename
    library: Library
    error_dialog: Adw.AlertDialog | None

    # templates
    toast_overlay: Adw.ToastOverlay = gtk_template_child()
    window_progress_bar: Gtk.ProgressBar = gtk_template_child()
    split_view: Adw.OverlaySplitView = gtk_template_child()
    library_list_box: Gtk.ListBox = gtk_template_child()
    library_view_stack: Adw.ViewStack = gtk_template_child()
    library_search_entry: Gtk.SearchEntry = gtk_template_child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rows = {}
        self.games = {}
        self.game_views = {}
        self.task_rows = {}

        self.app = self.get_application()  # pyright: ignore[reportAttributeAccessIssue]
        self.library = Library(self)
        self.library.connect('game-added', self._on_game_added)
        self.library.connect('game-changed', self._on_game_changed)
        self.library.connect('game-removed', self._on_game_removed)
        self.library.connect('task-started', self._on_task_started)
        self.library.connect('task-finished', self._on_task_finished)
        self.library.connect('message', self._on_message)

        self.ascending_order = False
        self.library_list_box.set_sort_func(self.sort_func)
        self.library_list_box.set_filter_func(self.filter_func)

        self.import_dialog = ImportDialog(self)
        self.settings_dialog = SettingsDialog(self)
        self.codename_dialog = RencherCodename(self)

        self.error_dialog = None

        GLib.idle_add(self.library.load_games)

    def _on_game_added(self, _, entry: GameEntry) -> None:
        row = GameRow(entry)
        self.rows[entry] = row
        self.games[row] = entry
        GLib.idle_add(self.library_list_box.append, row)
        self.split_view.set_show_sidebar(True)
        if not self.library_list_box.get_selected_row():
            self.library_view_stack.set_visible_child_name('game-select')

    def _on_game_changed(self, _, entry: GameEntry) -> None:
        entry.refresh()

    def _on_game_removed(self, _, entry: GameEntry) -> None:
        row = self.rows.pop(entry, None)
        if row:
            was_selected = row == self.library_list_box.get_selected_row()
            next_row = row.get_next_sibling() or row.get_prev_sibling()

            self.games.pop(row, None)
            GLib.idle_add(self.library_list_box.remove, row)

            if was_selected and next_row:
                GLib.idle_add(self.library_list_box.select_row, next_row)

        if len(self.library.store) == 0:
            self.library_view_stack.set_visible_child_name('empty')
            self.split_view.set_show_sidebar(False)

        if self.game_views.get(entry, None):
            self.game_views.pop(entry)

    def _on_task_started(self, _, task: RencherTask, entry: GameEntry | None):
        if entry:
            if not (row := self.rows.get(entry)):
                row = GameRow(entry)
                self.rows[entry] = row
                self.library_list_box.append(row)
                self.task_rows[task] = row
        else:
            row = GameRow(None, task.label)
            self.library_list_box.append(row)
            self.task_rows[task] = row

        row.set_task(task)

    def _on_task_finished(self, _, task: RencherTask, entry: GameEntry | None) -> None:
        row = self.task_rows.pop(task, None)
        if not row:
            return

        if entry:
            if not row.entry:  # it finished the task! yay
                row.set_entry(entry)
                row.set_task(None)
                self.rows[entry] = row
                self.games[row] = entry

    def _on_message(self, _, text: str):
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    @gtk_template_callback
    def on_import_clicked(self, *_) -> None:
        self.import_dialog.do_show()
        self.import_dialog.present(self)

    @gtk_template_callback
    def on_game_selected(self, _widget: Gtk.ListBox, row: GameRow | None) -> None:
        if row:
            if entry := self.games.get(row):
                view = self.game_views.get(entry, None)

                if not view:
                    view = GameDetailView(entry, self.app.rpc, row)
                    self.game_views[entry] = view
                    self.library_view_stack.add_named(view, entry.rpath)

                self.library_view_stack.set_visible_child_name(entry.rpath)
        else:
            self.library_view_stack.set_visible_child_name('game-select')

    @gtk_template_callback
    def on_search_changed(self, _widget: Gtk.SearchEntry):
        self.filter_text = _widget.get_text()
        self.library_list_box.invalidate_filter()

    @gtk_template_callback
    def on_combo_changed(self, _widget: Gtk.DropDown, _):
        self.combo_index = SortComboEnum(_widget.get_selected())
        self.library_list_box.invalidate_sort()

    @gtk_template_callback
    def on_order_changed(self, _widget: Gtk.ToggleButton):
        self.ascending_order = _widget.get_active()
        self.library_list_box.invalidate_sort()

    @gtk_template_callback
    def on_search_toggled(self, _widget: Gtk.ToggleButton):
        if not _widget.get_active():
            self.library_search_entry.set_text('')

    def filter_func(self, widget: GameRow) -> bool:
        if not self.filter_text:
            return True
        elif self.filter_text.lower() in widget.button_row.get_title().lower():
            return True
        else:
            return False

    def sort_func(self, one: GameRow, two: GameRow) -> int:
        entry_one = self.games.get(one, None)
        entry_two = self.games.get(two, None)
        if not entry_one or not entry_one.game or not entry_two or not entry_two.game:
            return 0

        one_value: str | int | float
        two_value: str | int | float

        if self.combo_index == SortComboEnum.NAME:
            one_value = entry_one.name.lower()
            two_value = entry_two.name.lower()
        elif self.combo_index == SortComboEnum.LAST_PLAYED:
            one_value = entry_one.game.config.get_value('last_played') or 0.0
            two_value = entry_two.game.config.get_value('last_played') or 0.0
        elif self.combo_index == SortComboEnum.PLAYTIME:
            one_value = entry_one.game.config.get_value('playtime') or 0.0
            two_value = entry_two.game.config.get_value('playtime') or 0.0
        elif self.combo_index == SortComboEnum.ADDED_ON:
            one_value = entry_one.game.config.get_value('added_on') or 0.0
            two_value = entry_two.game.config.get_value('added_on') or 0.0
        else:
            return 0

        if one_value < two_value:  # pyright: ignore[reportOperatorIssue]
            res = 1
        elif one_value > two_value:  # pyright: ignore[reportOperatorIssue]
            res = -1
        else:
            res = 0

        # 'b' > 'a' so we need to invert these
        if self.ascending_order and self.combo_index == SortComboEnum.NAME:
            return res
        elif self.ascending_order:
            return -res
        elif self.combo_index == SortComboEnum.NAME:
            return -res
        else:
            return res
