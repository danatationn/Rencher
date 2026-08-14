import logging
import os
import threading
from collections.abc import Callable
from configparser import ConfigParser
from typing import override

import gi
import requests
from rich.logging import RichHandler

import rencher
from rencher.gtk.rpc import Rpc
from rencher.renpy.config import RencherConfig

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from rencher.gtk.window import MainWindow  # noqa: E402
from rencher.renpy.paths import local_path  # noqa: E402


class MainApplication(Adw.Application):
    config: ConfigParser
    window: MainWindow

    rpc: Rpc

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            **kwargs,
            application_id='com.github.danatationn.rencher',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.NON_UNIQUE,
        )

        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Enable verbose output')
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Prints version')

        os.makedirs(local_path, exist_ok=True)

        rich_handler = RichHandler()
        rich_handler.setLevel(logging.INFO)
        rich_handler.set_name('rich_handler')
        rich_handler.setFormatter(logging.Formatter('%(message)s'))

        file_handler = logging.FileHandler(os.path.join(local_path, 'log.txt'), mode='w')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter('%(levelname)s:%(asctime)s:%(module)s %(message)s'))

        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[rich_handler, file_handler],
        )

        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.WARNING)

        actions: list[tuple[str, Callable[[Gio.SimpleAction, GLib.Variant | None], None], list[str]]] = [
            ('show-import', self.on_show_import, ['<Primary>plus']),
            ('show-preferences', self.on_show_preferences, ['<Primary>comma']),
            ('show-shortcuts', self.on_show_shortcuts, ['<Primary>question']),
            ('show-about', self.on_show_about, []),
            ('quit', self.on_quit, ['<Primary>q', '<Primary>w']),
        ]

        for name, callback, accels in actions:
            simple_action = Gio.SimpleAction.new(name, None)
            simple_action.connect('activate', callback)
            self.add_action(simple_action)
            if accels:
                self.set_accels_for_action(f'app.{name}', accels)

        self.rpc = Rpc(1485229562123124818)
        self.rpc.start()

    @override
    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        if options.contains('verbose') and (handler := logging.getHandlerByName('rich_handler')):
            handler.setLevel(logging.DEBUG)
        if options.contains('version'):
            print(rencher.__version__)
            return 0

        self.activate()
        return 0

    @override
    def do_activate(self):
        Adw.Application.do_activate(self)

        self.config = RencherConfig()
        self.window = MainWindow(application=self)
        self.window.present()

        if self.config['settings']['suppress_updates'] != 'true':
            version_thread = threading.Thread(target=self.check_version)
            version_thread.start()

    def on_show_import(self, *_):
        self.window.on_import_clicked()

    def on_show_preferences(self, *_):
        self.window.settings_dialog.on_show()
        self.window.settings_dialog.present(self.window)

    def on_show_shortcuts(self, *_):
        builder = Gtk.Builder.new_from_resource('/com/github/danatationn/rencher/ui/shortcuts.ui')
        dialog: Adw.ShortcutsDialog = builder.get_object('RencherShortcuts')
        dialog.present(self.window)

    @override
    def do_shutdown(self) -> None:
        self.rpc.stop()
        Gtk.Application.do_shutdown(self)

    def on_quit(self, *_):
        self.quit()

    def on_show_about(self, *_):
        log_path = os.path.join(local_path, 'log.txt')
        with open(log_path) as f:
            debug_info = f.read()
        dialog = Adw.AboutDialog(
            application_icon='com.github.danatationn.rencher',
            application_name='Rencher',
            developer_name='danatationn',
            version=rencher.__version__,
            comments=rencher.__description__,
            website=rencher.__url__,
            issue_url=rencher.__issue_url__,
            support_url=rencher.__issue_url__,
            copyright=rencher.__copyright__,
            license_type=Gtk.License.GPL_3_0_ONLY,
            developers=['danatationn'],
            designers=['danatationn', 'vl1'],
            debug_info=debug_info,
            debug_info_filename='log.txt',
            release_notes="""<ul>
                <li> Fixed Logs row not collapsing after starting a new game </li>
                <li> Fixed "Delete Files on Import" not working with archives </li>
            </ul>""",
            release_notes_version=rencher.__version__,
        )

        dialog.present(self.window)

    def check_version(self, show_up_to_date_toast: bool = False) -> None:
        try:
            response = requests.get('https://api.github.com/repos/danatationn/rencher/releases/latest')
        except requests.exceptions.ConnectionError:
            return
        else:
            if response.status_code == 404:
                return
            version_str = response.json()['tag_name'].replace('v', '')
            upstream_version = tuple(map(int, version_str.split('.')))
            rencher_version = tuple(map(int, rencher.__version__.split('.')))

            toast = Adw.Toast(timeout=5)

            if upstream_version > rencher_version:
                if 'assets' in response.json() and len(response.json()['assets']) > 0:
                    download_url = response.json()['html_url']
                else:
                    return

                logging.info(f'A new update is available! (v{version_str})')
                logging.info(download_url)
                toast.set_title(f'A new update is available! (v{version_str})')
                toast.set_button_label('Download')
                toast.connect('button-clicked', lambda *_: Gtk.show_uri(self.window, download_url, Gdk.CURRENT_TIME))

                GLib.idle_add(self.window.toast_overlay.add_toast, toast)
            elif upstream_version == rencher_version:
                toast.set_title(f"You're up to date! (v{rencher.__version__})")
            else:
                toast.set_title(f"You're bleeding-edge! (v{rencher.__version__})")

            if show_up_to_date_toast:
                GLib.idle_add(self.window.toast_overlay.add_toast, toast)
            logging.info(toast.get_title())
