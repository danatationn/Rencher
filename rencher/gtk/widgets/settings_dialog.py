import os.path
import platform
import threading
from pathlib import Path
from typing import TYPE_CHECKING, override

from gi.repository import Adw, GLib, Gtk

from rencher.gtk.utils import open_file_manager
from rencher.renpy.config import RencherConfig
from rencher.renpy.paths import local_path

if TYPE_CHECKING:
    from rencher.gtk.window import MainWindow

@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/settings.ui')
class SettingsDialog(Adw.PreferencesDialog):
    __gtype_name__: str = 'SettingsDialog'

    window: 'MainWindow'
    config: RencherConfig

    data_dir_entry: Adw.EntryRow = Gtk.Template.Child()
    updates_switch: Adw.SwitchRow = Gtk.Template.Child()
    delete_import_switch: Adw.SwitchRow = Gtk.Template.Child()
    skip_splash_scr_switch: Adw.SwitchRow = Gtk.Template.Child()
    skip_main_menu_switch: Adw.SwitchRow = Gtk.Template.Child()
    forced_save_dir_switch: Adw.SwitchRow = Gtk.Template.Child()
    windowficate_switch: Adw.SwitchRow = Gtk.Template.Child()
    discord_rpc_switch: Adw.SwitchRow = Gtk.Template.Child()
    switches_list: list[tuple[Adw.SwitchRow, str]]

    def __init__(self, window: 'MainWindow', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.switches_list = [
            (self.delete_import_switch, 'delete_on_import'),
            (self.updates_switch, 'suppress_updates'),
            (self.skip_splash_scr_switch, 'skip_splash_scr'),
            (self.skip_main_menu_switch, 'skip_main_menu'),
            (self.forced_save_dir_switch, 'forced_save_dir'),
            (self.windowficate_switch, 'windowficate_filenames'),
            (self.discord_rpc_switch, 'discord_rpc'),
        ]

        self.window = window
        if platform.system() == 'Windows':
            self.windowficate_switch.set_visible(False)  # force it on

    def on_show(self):
        self.config = RencherConfig()

        if self.config['settings']['data_dir'] == '':
            self.data_dir_entry.set_text(str(local_path))
        else:
            self.data_dir_entry.set_text(self.config['settings']['data_dir'])

        for switch, key in self.switches_list:
            if self.config['settings'][key] == 'true':
                switch.set_active(True)

    @override
    def do_closed(self):
        old_data_dir = self.config['settings']['data_dir']

        if self.data_dir_entry.get_text() == str(local_path):
            self.config['settings']['data_dir'] = ''
        else:
            self.config['settings']['data_dir'] = self.data_dir_entry.get_text()

        for switch, key in self.switches_list:
            if switch.get_active():
                self.config['settings'][key] = 'true'
            else:
                self.config['settings'][key] = 'false'

        self.config.write()

        if self.config['settings']['data_dir'] != old_data_dir:
            self.window.library.load_games()

    @Gtk.Template.Callback()
    def on_picker_clicked(self, _widget: Gtk.Button):
        dialog = Gtk.FileDialog()
        dialog.select_folder(self.window, None, self.on_folder_selected)

    @Gtk.Template.Callback()
    def on_dir_clicked(self, _):
        data_dir = self.data_dir_entry.get_text()
        open_file_manager(data_dir)

    def on_folder_selected(self, dialog: Gtk.FileDialog, result):
        try:
            folder = dialog.select_folder_finish(result)
        except GLib.Error:
            pass  # dialog was dismissed by user
        else:
            path = folder.get_path()
            self.data_dir_entry.set_text(path if path else '')

    @Gtk.Template.Callback()
    def on_check_updates(self, _):
        thread = threading.Thread(target=lambda: self.window.app.check_version(show_up_to_date_toast=True))
        thread.start()
        self.close()

    @Gtk.Template.Callback()
    def on_reset_data_dir(self, _widget: Adw.ButtonRow):  # type: ignore
        self.data_dir_entry.set_text(str(local_path))

    @Gtk.Template.Callback()
    def on_delete_games(self, _widget: Adw.ButtonRow):  # type: ignore
        dialog = Adw.AlertDialog(
            heading='Are you sure?',
            body='This will delete ALL the games in your data directory.\nThis action cannot be undone.',
        )
        dialog.add_response('cancel', 'No')
        dialog.add_response('ok', 'Yes')
        dialog.set_response_appearance('ok', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_close_response('cancel')
        dialog.set_default_response('cancel')
        dialog.connect('response', self.nuke_games)
        dialog.choose(self)

    def nuke_games(self, _, response: str):
        if response != 'ok':
            return
        data_dir = Path(self.data_dir_entry.get_text())
        games_dir = data_dir / 'games'

        def nuke_thread():
            toast = Adw.Toast(title='All games have been successfully deleted', timeout=5)
            total_work = 0
            completed = 0
            rpaths: list[str] = []

            for _, dirs, files in os.walk(games_dir):
                for _ in dirs:
                    total_work += 1
                for _ in files:
                    total_work += 1

            # task = self.window.tasks_popover.new_task('', TaskTypeEnum.NUKE, None, total_work)

            for _, dirs, _ in os.walk(games_dir):
                for dir in dirs:
                    path = os.path.join(games_dir, dir)
                    rpaths.append(path)
                break

            for root, dirs, files in os.walk(games_dir, topdown=False):
                for filename in files:
                    file = os.path.join(root, filename)
                    try:
                        os.unlink(file)
                    except PermissionError:
                        pass
                    except FileNotFoundError:
                        pass
                    completed += 1
                    # self.window.tasks_popover.update_task(task, completed)

                for dirname in dirs:
                    dir = os.path.join(root, dirname)
                    try:
                        os.rmdir(dir)
                    except PermissionError:
                        pass
                    except FileNotFoundError:
                        pass
                    completed += 1
                    # self.window.tasks_popover.update_task(task, completed)

                if root in rpaths:
                    GLib.idle_add(lambda r=root: self.window.library.remove_game(r))

            GLib.idle_add(lambda: (
                self.window.toast_overlay.add_toast(toast),
            ))

        thread = threading.Thread(target=nuke_thread)
        thread.start()
        self.close()
