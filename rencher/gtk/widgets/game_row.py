from gi.repository import Adw, GObject, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.tasks import RencherTask


class GameRow(Gtk.ListBoxRow):
    entry: GameEntry | None
    button_row: Adw.ButtonRow
    progress_bar: Gtk.ProgressBar
    _bindings: list[GObject.Binding]

    def __init__(self, entry: GameEntry | None = None, fallback_name: str = ''):
        super().__init__()

        if not entry and fallback_name == '':
            raise ValueError('entry or fallback_name are required')

        self.entry = entry
        self.button_row = Adw.ButtonRow()
        self._bindings = []

        if entry:
            entry.bind_property('name', self.button_row, 'title', GObject.BindingFlags.SYNC_CREATE)
        elif fallback_name != '':
            self.button_row.set_title(fallback_name)

        self.progress_bar = Gtk.ProgressBar(visible=False)
        self.progress_bar.add_css_class('osd')

        overlay = Gtk.Overlay()
        overlay.set_child(self.button_row)
        overlay.add_overlay(self.progress_bar)
        self.set_child(overlay)

    def set_entry(self, entry: GameEntry):
        if self.entry:
            self.entry.update(entry.game)
        else:
            self.entry = entry
        self.entry.bind_property('name', self.button_row, 'title', GObject.BindingFlags.SYNC_CREATE)

    def set_task(self, task: RencherTask | None):
        for binding in self._bindings:
            binding.unbind()
            self._bindings.remove(binding)

        if task:
            self._bindings.append(
                task.bind_property('fraction', self.progress_bar, 'fraction', GObject.BindingFlags.SYNC_CREATE)
            )
            self._bindings.append(
                task.bind_property('fraction', self.progress_bar, 'visible', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction < 1.0)
            )
            self._bindings.append(
                task.bind_property('fraction', self, 'selectable', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction == 1.0)
            )
            self._bindings.append(
                task.bind_property('fraction', self.button_row, 'sensitive', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction == 1.0)
            )
        else:
            self.progress_bar.set_visible(False)
            self.set_selectable(True)
            self.button_row.set_sensitive(True)
