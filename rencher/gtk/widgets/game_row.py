from gi.repository import Adw, GObject, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.tasks import RencherTask


class GameRow(Gtk.ListBoxRow):
    entry: GameEntry | None
    btn: Adw.ButtonRow
    pb: Gtk.ProgressBar
    _bindings: list[GObject.Binding]

    def __init__(self, entry: GameEntry | None = None, fallback_name: str = ''):
        super().__init__()

        if not entry and fallback_name == '':
            raise ValueError('entry or fallback_name are required')

        self.entry = entry
        self.btn = Adw.ButtonRow()
        self._bindings = []

        if entry:
            entry.bind_property('name', self.btn, 'title', GObject.BindingFlags.SYNC_CREATE)
        elif fallback_name != '':
            self.btn.set_title(fallback_name)

        self.pb = Gtk.ProgressBar(visible=False)
        self.pb.add_css_class('osd')

        overlay = Gtk.Overlay()
        overlay.set_child(self.btn)
        overlay.add_overlay(self.pb)
        self.set_child(overlay)

    def set_entry(self, entry: GameEntry):
        if self.entry:
            self.entry.update(entry.game)
        else:
            self.entry = entry
        self.entry.bind_property('name', self.btn, 'title', GObject.BindingFlags.SYNC_CREATE)

    def set_task(self, task: RencherTask | None):
        for binding in self._bindings:
            binding.unbind()
        self._bindings.clear()

        if task:
            self._bindings.append(
                task.bind_property('fraction', self.pb, 'fraction', GObject.BindingFlags.SYNC_CREATE)
            )
            self._bindings.append(
                task.bind_property('fraction', self.pb, 'visible', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction < 1.0)
            )
            self._bindings.append(
                task.bind_property('fraction', self, 'selectable', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction == 1.0)
            )
            self._bindings.append(
                task.bind_property('fraction', self, 'activatable', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction == 1.0)
            )
            self._bindings.append(
                task.bind_property('fraction', self.btn, 'sensitive', GObject.BindingFlags.SYNC_CREATE,
                                   lambda _binding, fraction: fraction == 1.0)
            )
        else:
            self.pb.set_visible(False)
            self.pb.set_fraction(0.0)
            self.set_selectable(True)
            self.set_activatable(True)
            self.btn.set_sensitive(True)

    @property
    def has_task(self) -> bool:
        return len(self._bindings) > 0
