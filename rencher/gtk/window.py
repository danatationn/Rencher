from enum import Enum
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.library import Library
from rencher.gtk.widgets.codename_dialog import RencherCodename
from rencher.gtk.widgets.game_detail_view import GameDetailView
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
    rows: dict[GameEntry, Gtk.ListBoxRow]
    games: dict[Gtk.ListBoxRow, GameEntry]
    game_views: dict[GameEntry, GameDetailView]

    filter_text: str = ''
    combo_index: int = 0
    ascending_order: bool

    # classes
    app: 'MainApplication'
    settings_dialog: SettingsDialog
    import_dialog: ImportDialog
    # options_dialog: OptionsDialog
    codename_dialog: RencherCodename
    library: Library
    error_dialog: Adw.AlertDialog | None

    # templates
    toast_overlay: Adw.ToastOverlay = Gtk.Template.Child()
    window_progress_bar: Gtk.ProgressBar = Gtk.Template.Child()
    split_view: Adw.OverlaySplitView = Gtk.Template.Child()
    library_list_box: Gtk.ListBox = Gtk.Template.Child()
    library_view_stack: Adw.ViewStack = Gtk.Template.Child()
    library_search_entry: Gtk.SearchEntry = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.rows = {}
        self.games = {}
        self.game_views = {}

        self.app = self.get_application()  # pyright: ignore[reportAttributeAccessIssue]
        self.library = Library(self)
        self.library.connect('game-added', self._on_game_added)
        self.library.connect('game-changed', self._on_game_changed)
        self.library.connect('game-removed', self._on_game_removed)

        self.ascending_order = False
        self.library_list_box.set_sort_func(self.sort_func)
        self.library_list_box.set_filter_func(self.filter_func)

        self.import_dialog = ImportDialog(self)
        # self.options_dialog = OptionsDialog(self)
        self.settings_dialog = SettingsDialog(self)
        self.codename_dialog = RencherCodename(self)

        self.error_dialog = None

        GLib.idle_add(self.library.load_games)

    def _on_game_added(self, _, entry: GameEntry) -> None:
        row = Adw.ButtonRow(title=entry.name)
        self.rows[entry] = row
        self.games[row] = entry
        GLib.idle_add(self.library_list_box.append, row)
        self.split_view.set_show_sidebar(True)
        if not self.library_list_box.get_selected_row():
            self.library_view_stack.set_visible_child_name('game-select')

    def _on_game_changed(self, _, entry: GameEntry) -> None:

        ...

        entry.refresh(entry.game)

        if row := self.rows.get(entry, None):
            GLib.idle_add(row.set_title, entry.name)  # pyright: ignore[reportAttributeAccessIssue]

    def _on_game_removed(self, _, entry: GameEntry) -> None:
        row = self.rows.pop(entry, None)
        if row:
            self.games.pop(row, None)
            GLib.idle_add(self.library_list_box.remove, row)

        if self.game_views.get(entry, None):
            self.game_views.pop(entry)

        if len(self.library.store) == 0:
            self.library_view_stack.set_visible_child_name('empty')
            self.split_view.set_show_sidebar(False)

    @Gtk.Template.Callback()
    def on_import_clicked(self, *_) -> None:
        self.import_dialog.do_show()
        self.import_dialog.present(self)

    @Gtk.Template.Callback()
    def on_game_selected(self, _widget: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row:
            if entry := self.games.get(row):
                view = self.game_views.get(entry, None)

                if not view:
                    view = GameDetailView(entry, self.app.rpc)
                    self.game_views[entry] = view
                    self.library_view_stack.add_named(view, entry.rpath)

                self.library_view_stack.set_visible_child_name(entry.rpath)
        else:
            self.library_view_stack.set_visible_child_name('game-select')

    @Gtk.Template.Callback()
    def on_search_changed(self, _widget: Gtk.SearchEntry):
        self.filter_text = _widget.get_text()
        self.library_list_box.invalidate_filter()

    @Gtk.Template.Callback()
    def on_combo_changed(self, _widget: Gtk.DropDown, _):
        self.combo_index = _widget.get_selected()
        self.library_list_box.invalidate_sort()

    @Gtk.Template.Callback()
    def on_order_changed(self, _widget: Gtk.ToggleButton):
        self.ascending_order = _widget.get_active()
        self.library_list_box.invalidate_sort()

    @Gtk.Template.Callback()
    def on_search_toggled(self, _widget: Gtk.ToggleButton):
        if not _widget.get_active():
            self.library_search_entry.set_text('')

    def filter_func(self, widget: Adw.ButtonRow) -> bool:
        if not self.filter_text:
            return True
        elif self.filter_text.lower() in widget.get_title().lower():
            return True
        else:
            return False

    def sort_func(self, one: Adw.ActionRow, two: Adw.ActionRow) -> int:
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
            one_value = entry_one.game.config['info'].get('last_played', 0)
            two_value = entry_two.game.config['info'].get('last_played', 0)
        elif self.combo_index == SortComboEnum.PLAYTIME:
            one_value = float(entry_one.game.config['info'].get('playtime', 0))
            two_value = float(entry_two.game.config['info'].get('playtime', 0))
        elif self.combo_index == SortComboEnum.ADDED_ON:
            one_value = entry_one.game.config['info'].get('added_on', 0)
            two_value = entry_two.game.config['info'].get('added_on', 0)
        else:
            return 0

        if str(one_value) < str(two_value):
            res = 1
        elif str(one_value) > str(two_value):
            res = -1
        else:
            res = 0

        # 'b' > 'a' so we need to invert these
        if self.ascending_order != self.combo_index == 0:
            return res
        elif self.ascending_order:
            return -res
        elif self.combo_index == 0:
            return -res
        else:
            return res
