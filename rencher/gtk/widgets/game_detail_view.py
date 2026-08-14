import subprocess
import threading
import time
from typing import IO

from gi.repository import Adw, GLib, GObject, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.rpc import Rpc
from rencher.gtk.utils import open_file_manager
from rencher.gtk.widgets.options_dialog import OptionsDialog


@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/game_detail_view.ui')
class GameDetailView(Gtk.Box):
    __gtype_name__: str = 'GameDetailView'

    title_status_page: Adw.StatusPage = Gtk.Template.Child()
    last_played_row: Adw.ActionRow = Gtk.Template.Child()
    playtime_row: Adw.ActionRow = Gtk.Template.Child()
    added_on_row: Adw.ActionRow = Gtk.Template.Child()
    rpath_row: Adw.ActionRow = Gtk.Template.Child()
    version_row: Adw.ActionRow = Gtk.Template.Child()
    codename_row: Adw.ActionRow = Gtk.Template.Child()
    log_row: Adw.ExpanderRow = Gtk.Template.Child()
    log_text_view: Gtk.TextView = Gtk.Template.Child()

    entry: GameEntry
    rpc: Rpc
    log_buf: Gtk.TextBuffer

    game_process: subprocess.Popen[bytes] | None
    process_time: float
    is_terminating: bool

    play_button: Gtk.Button = Gtk.Template.Child()
    error_dialog: Adw.AlertDialog | None
    options_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self, entry: GameEntry, rpc: Rpc, **kwargs):
        super().__init__(**kwargs)
        self.entry = entry
        self.rpc = rpc
        self.log_buf = self.log_text_view.get_buffer()

        self.process_time = -1.0

        self.game_process = None
        self.is_terminating = False
        self.error_dialog = None

        # to change the labels when the view is created, we need GObject.BindingFlags.SYNC_CREATE
        # or else it only updates when something changes
        self.entry.bind_property('name', self.title_status_page, 'title', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('last_played', self.last_played_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('playtime', self.playtime_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('added_on', self.added_on_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('version', self.version_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('rpath', self.rpath_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)
        self.entry.bind_property('codename', self.codename_row, 'subtitle', GObject.BindingFlags.SYNC_CREATE)

        self.log_buf = self.log_text_view.get_buffer()
        self.log_buf.create_tag("stderr", foreground="orange")
        self.log_buf.connect('changed', lambda b: self.log_row.set_sensitive(b.get_char_count() > 0))

        GLib.timeout_add(250, self.check_process)

    @Gtk.Template.Callback()
    def on_play_clicked(self, play_button: Gtk.Button) -> None:
        if not self.entry.game.is_launchable:
            alert = Adw.AlertDialog(heading='Error', body='This game has no valid executables!')
            alert.add_response('ok', 'OK')
            alert.choose(self)
            return

        if play_button.get_style_context().has_class('suggested-action'):
            try:
                self.game_process = self.entry.game.run()
            except PermissionError:
                alert = Adw.AlertDialog(heading='Error', body='This game\'s executable is not executable!')
                alert.add_response('ok', 'OK')
                alert.choose(self)
            else:
                self.log_row.set_expanded(False)
                self.log_buf.set_text('')
                threading.Thread(target=self._read_stream, args=(self.game_process.stdout, False), daemon=True).start()
                threading.Thread(target=self._read_stream, args=(self.game_process.stderr, True), daemon=True).start()
                self.process_time = time.time()
                self.check_process()  # so the button changes instantly
        else:
            if self.game_process:
                self.play_button.set_label('Stopping')
                self.is_terminating = True
                self.game_process.terminate()

    def _read_stream(self, stream: IO[bytes], is_stderr: bool) -> None:
        for line in stream:
            GLib.idle_add(self._on_log_line, line.decode(errors='replace'), is_stderr)

    def _on_log_line(self, line: str, is_stderr: bool) -> None:
        if is_stderr:
            self.log_buf.insert_with_tags_by_name(self.log_buf.get_end_iter(), line, "stderr")
        else:
            self.log_buf.insert(self.log_buf.get_end_iter(), line)
        self.log_text_view.scroll_to_iter(self.log_buf.get_end_iter(), 0, False, 0, 0)

    def _on_error_dialog_response(self, _, id: str):
        if id == 'show':
            GLib.idle_add(self.log_row.set_expanded, True)
            GLib.idle_add(self.log_text_view.grab_focus)

    # TODO scroll to the *bottom* of the log view . not the top
    def _scroll_to_log(self) -> None:
        scrolled_window = self.log_text_view.get_parent()
        if isinstance(scrolled_window, Gtk.ScrolledWindow):
            adj = scrolled_window.get_vadjustment()
            adj.set_value(adj.get_upper() - adj.get_page_size())

    @Gtk.Template.Callback()
    def on_dir_clicked(self, _widget: Gtk.Button) -> None:
        open_file_manager(self.entry.apath)

    @Gtk.Template.Callback()
    def on_options_clicked(self, _widget: Gtk.Button):
        # TODO info used to get changed via filemonitor. think of a way to update gamedetailview info
        options_dialog = OptionsDialog(self.entry)
        options_dialog.present(self)

    def check_process(self) -> bool:
        if not self.game_process or self.game_process.poll() is not None:
            # game not launched yet / game stopped
            self.play_button.set_label('Play')
            self.play_button.get_style_context().remove_class('destructive-action')
            self.play_button.get_style_context().add_class('suggested-action')
            # self.options_button.set_sensitive(True)
            self.is_terminating = False

            # i have no idea how these checks would ever change but i'll keep them ig
            if self.game_process is not None:
                self.rpc.clear()

            if self.game_process is None:
                return True

            playtime = self.entry.game.config.get_value('playtime')
            if self.process_time and isinstance(playtime, float):
                playtime += time.time() - self.process_time
                self.entry.game.cleanup(playtime)

            # non-zero exit codes are errors. if you didn't know. a lot of people don't know this
            # TODO check if logs is empty
            if self.game_process.returncode != 0:
                self.error_dialog = Adw.AlertDialog(
                    heading='Something went wrong!',
                    body='A game has errors. Check the logs for more details.',
                    default_response='show',
                    close_response='cancel',
                )
                self.error_dialog.add_response('show', 'Show Logs')
                self.error_dialog.add_response('cancel', 'Cancel')
                self.error_dialog.connect('response', self._on_error_dialog_response)
                GLib.idle_add(self.error_dialog.present, self)

            self.game_process = None
        else:
            if self.is_terminating:
                self.play_button.set_label('Stopping')
            else:
                self.play_button.set_label('Stop')
                if self.game_process and self.entry.game.config['overwritten']['discord_rpc'] == 'true':
                    self.rpc.update(state=self.entry.name)
            self.play_button.get_style_context().remove_class('suggested-action')
            self.play_button.get_style_context().add_class('destructive-action')
            # self.options_button.set_sensitive(False)
        return True
