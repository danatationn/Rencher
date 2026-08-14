import logging
import os
import threading
from configparser import ConfigParser
from pathlib import Path
from typing import override

from gi.repository import Adw, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.utils import open_file_manager
from rencher.renpy.config import RencherConfig
from rencher.renpy.paths import get_py_files


@Gtk.Template.from_resource('/com/github/danatationn/rencher/ui/options.ui')
class OptionsDialog(Adw.PreferencesDialog):
    __gtype_name__: str = 'OptionsDialog'

    nickname_entry: Adw.EntryRow = Gtk.Template.Child()
    location_row: Adw.ActionRow = Gtk.Template.Child()
    codename_combo: Adw.ComboRow = Gtk.Template.Child()
    skip_splash_scr_switch: Adw.SwitchRow = Gtk.Template.Child()
    skip_main_menu_switch: Adw.SwitchRow = Gtk.Template.Child()
    forced_save_dir_switch: Adw.SwitchRow = Gtk.Template.Child()
    discord_rpc_switch: Adw.SwitchRow = Gtk.Template.Child()
    overwrite_skip_splash_scr_switch: Gtk.Switch = Gtk.Template.Child()
    overwrite_skip_main_menu_switch: Gtk.Switch = Gtk.Template.Child()
    overwrite_forced_save_dir_switch: Gtk.Switch = Gtk.Template.Child()
    overwrite_discord_rpc_switch: Gtk.Switch = Gtk.Template.Child()
    switches_list: list[tuple[Gtk.Switch, Adw.SwitchRow, str]]
    # options_save_slot: Adw.SpinRow = Gtk.Template.Child()

    entry: GameEntry
    rencher_config: ConfigParser

    def __init__(self, entry: GameEntry):
        super().__init__()

        self.entry = entry

        self.switches_list = [
            (self.overwrite_skip_splash_scr_switch, self.skip_splash_scr_switch, 'skip_splash_scr'),
            (self.overwrite_skip_main_menu_switch, self.skip_main_menu_switch, 'skip_main_menu'),
            (self.overwrite_forced_save_dir_switch, self.forced_save_dir_switch, 'forced_save_dir'),
            (self.overwrite_discord_rpc_switch, self.discord_rpc_switch, 'discord_rpc'),
        ]

        # self.options_save_slot.set_adjustment(Gtk.Adjustment(
        #     lower=1,
        #     upper=10,
        #     value=1,
        #     step_increment=1,
        #     page_increment=10,
        # ))

        self.change_game(entry)

    def change_game(self, entry: GameEntry):
        self.entry.refresh(entry.game)
        string_list = Gtk.StringList()
        self.codename_combo.set_model(string_list)

        self.rencher_config = RencherConfig()

        self.nickname_entry.set_text(entry.name)
        self.location_row.set_subtitle(str(entry.rpath))
        # self.options_save_slot.set_text(game.config['options']['save_slot'])

        py_files = get_py_files(entry.apath)

        codename_index = None
        for i, path in enumerate(py_files):
            codename = os.path.splitext(os.path.basename(path))[0]
            string_list.append(codename)
            if codename == entry.config['info']['codename']:
                codename_index = i

        self.codename_combo.set_model(string_list)
        if codename_index:
            self.codename_combo.set_selected(codename_index)

        for overwrite_switch, switch, key in self.switches_list:
            if entry.config['options'][key] != '':  # overwritten
                overwrite_switch.set_active(True)
                if entry.config['options'][key] == 'true':
                    switch.set_active(True)
                else:
                    switch.set_active(False)
            elif self.rencher_config['settings'][key] == 'true':  # default
                switch.set_active(True)
                overwrite_switch.set_active(False)
            else:
                overwrite_switch.set_active(False)
                switch.set_active(False)

    @override
    def do_closed(self):
        if not Path(self.entry.rpath).is_dir():
            return  # it got deleted

        sel_codename = self.codename_combo.get_selected_item()
        logging.debug(type(sel_codename))
        if not isinstance(sel_codename, Gtk.StringObject):
            logging.error('TODO something has no scripts')
            return

        if self.entry.name != self.nickname_entry.get_text():
            self.entry.config['info']['nickname'] = self.nickname_entry.get_text()
        if self.entry.codename != sel_codename.get_string():
            self.entry.config['info']['codename'] = sel_codename.get_string()
        # self.game.config['options']['save_slot'] = self.options_save_slot.get_text()

        for overwrite_switch, switch, key in self.switches_list:
            if overwrite_switch.get_active():
                if switch.get_active():
                    self.entry.config['options'][key] = 'true'
                    self.entry.config['overwritten'][key] = 'true'
                else:
                    self.entry.config['options'][key] = 'false'
                    self.entry.config['overwritten'][key] = 'false'
            else:
                self.entry.config['options'][key] = ''
                self.entry.config['overwritten'][key] = self.rencher_config['settings'][key]

        self.entry.config.write()

    @Gtk.Template.Callback()
    def on_switch_changed(self, _widget: Gtk.Switch | Adw.SwitchRow, _):
        for overwrite_switch, switch, key in self.switches_list:
            if _widget == overwrite_switch:
                current_value = self.rencher_config['settings'][key]
                if current_value == 'true':
                    switch.set_active(True)
                else:
                    switch.set_active(False)

    @Gtk.Template.Callback()
    def on_dir_clicked(self, _widget: Gtk.Button):
        open_file_manager(str(self.entry.rpath))

    @Gtk.Template.Callback()
    def on_clear_info(self, _widget: Adw.ButtonRow):  # type: ignore
        dialog = Adw.AlertDialog(
            heading='Are you sure?',
            body=f'This will permanently reset all user data for "{self.game.name}".\nThis action cannot be undone.',
        )
        dialog.add_response('cancel', 'No')
        dialog.add_response('ok', 'Yes')
        dialog.set_response_appearance('ok', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self)
        dialog.connect('response', self.on_clear_info_response)

    def on_clear_info_response(self, _, response: str):
        if response == 'ok':
            # slaughter time
            self.entry.config['info']['nickname'] = ''
            self.entry.config['info']['last_played'] = ''
            self.entry.config['info']['playtime'] = '0.0'

            self.entry.config['options']['skip_splash_scr'] = ''
            self.entry.config['options']['skip_main_menu'] = ''
            self.entry.config['options']['forced_save_dir'] = ''

            # self.game.config.write_config()

            # TODO think how to do this
            # toast = Adw.Toast(
            #     title=f'"{self.entry.name}" stats have been reset',
            #     timeout=5,
            # )
            # self.window.toast_overlay.add_toast(toast)

    @Gtk.Template.Callback()
    def on_delete_game(self, _widget: Adw.ButtonRow):  # type: ignore
        dialog = Adw.AlertDialog(
            heading='Are you sure?',
            body=f'This will permanently delete "{self.game.name}".\nThis action cannot be undone.',
        )
        dialog.add_response('cancel', 'No')
        dialog.add_response('ok', 'Yes')
        dialog.set_response_appearance('ok', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self)
        dialog.connect('response', self.on_delete_game_response)

    def on_delete_game_response(self, _, response: str):
        if response != 'ok':
            return

        def delete_thread():
            # GLib.idle_add(self.window.library.remove_game, self.game.rpath)
            toast = Adw.Toast(title=f'"{self.entry.name}" has been deleted', timeout=5)
            # task_date = time.time()
            total_work = 0
            completed = 0

            for _, dirs, files in os.walk(self.entry.rpath):
                for _ in dirs:
                    total_work += 1
                for _ in files:
                    total_work += 1

            # task = self.window.tasks_popover.new_task(self.game.name, TaskTypeEnum.DELETE, None, total_work)

            for root, dirs, files in os.walk(self.entry.rpath, topdown=False):
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

            try:
                os.rmdir(self.entry.rpath)
            except PermissionError:
                pass
            except FileNotFoundError:
                pass

            # GLib.idle_add(lambda: (
            #     self.window.library.remove_game(self.entry.rpath),
            #     self.window.toast_overlay.add_toast(toast),
            # ))

        thread = threading.Thread(target=delete_thread)
        thread.start()
        self.close()
