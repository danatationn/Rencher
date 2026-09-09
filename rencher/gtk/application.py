import importlib.metadata
import logging
import os
import threading
from collections.abc import Callable
from configparser import ConfigParser
from typing import Any, NotRequired, TypedDict, cast, override

import gi
import requests
from rich.logging import RichHandler

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
    simple_actions: dict[str, Gio.SimpleAction]

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

        local_path.mkdir(parents=True, exist_ok=True)

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
            ('refresh-games', self.on_refresh_games, ['<Primary>r']),
        ]
        self.simple_actions = {}

        for name, callback, accels in actions:
            simple_action = Gio.SimpleAction.new(name, None)
            simple_action.connect('activate', callback)
            self.add_action(simple_action)
            self.simple_actions[name] = simple_action
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
            print(importlib.metadata.version('rencher'))
            return 0

        self.activate()
        return 0

    @override
    def do_activate(self):
        Adw.Application.do_activate(self)

        self.config = RencherConfig()
        self.window = MainWindow(application=self)
        self.window.present()

        event_controller_key = Gtk.EventControllerKey.new()
        event_controller_key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        event_controller_key.connect('key-pressed', self.on_key_pressed)
        event_controller_key.connect('key-released', self.on_key_released)
        self.window.add_controller(event_controller_key)

        if self.config['settings']['suppress_updates'] != 'true':
            version_thread = threading.Thread(target=self.check_version)
            version_thread.start()

    def on_key_pressed(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_r and (state & Gdk.ModifierType.CONTROL_MASK):
            refresh_action = self.simple_actions['refresh-games']
            if refresh_action.get_enabled():
                refresh_action.activate()
                refresh_action.set_enabled(False)
            return True
        return False

    def on_key_released(
        self, _controller: Gtk.EventControllerKey, keyval: int, _keycode: int, _state: Gdk.ModifierType,
    ) -> None:
        if keyval == Gdk.KEY_r:
            self.simple_actions['refresh-games'].set_enabled(True)

    def on_show_import(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        self.window.on_import_clicked()

    def on_refresh_games(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        logging.info(f'Refreshing games from "{RencherConfig().get_data_dir()}"...')
        GLib.idle_add(self.window.library.load_games)

    def on_show_preferences(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        self.window.settings_dialog.on_show()
        self.window.settings_dialog.present(self.window)

    def on_show_shortcuts(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        builder = Gtk.Builder.new_from_resource('/com/github/danatationn/rencher/ui/shortcuts.ui')
        # why aren't stubs updated yet
        dialog: Adw.ShortcutsDialog = builder.get_object('RencherShortcuts')  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        dialog.present(self.window)  # pyright: ignore[reportUnknownMemberType]

    @override
    def do_shutdown(self) -> None:
        self.rpc.stop()
        Gtk.Application.do_shutdown(self)

    def on_quit(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        self.quit()

    def on_show_about(self, _action: Gio.SimpleAction, _variant: GLib.Variant | None) -> None:
        log_path = os.path.join(local_path, 'log.txt')
        debug_info: str

        with open(log_path) as f:
            debug_info = f.read()

        meta = importlib.metadata.metadata('rencher')
        version = importlib.metadata.version('rencher')
        description = meta['Summary']

        urls: dict[str, str] = {}
        for entry in cast('list[str]', meta.get_all('Project-URL') or []):
            label, url = entry.split(',', 1)
            urls[label.strip().lower()] = url.strip()

        homepage = urls['homepage']
        issue_url = urls['issues']

        dialog = Adw.AboutDialog(
            application_icon='com.github.danatationn.rencher',
            application_name='Rencher',
            developer_name='danatationn',
            version=version,
            comments=description,
            website=homepage,
            issue_url=issue_url,
            support_url=issue_url,
            copyright='© 2026 danatationn',
            license_type=Gtk.License.GPL_3_0_ONLY,
            developers=['danatationn'],
            designers=['danatationn', 'vl1'],
            debug_info=debug_info,
            debug_info_filename='log.txt',
            release_notes="""<ul>
                <li>Fixed log dialog appearing when stopping a game early</li>
                <li>Completely reworked the tasks system</li>
                <li>Removed file monitoring</li>
                <li>Added refresh games button</li>
            </ul>""",
            release_notes_version=version,
        )

        dialog.present(self.window)

    def check_version(self, show_up_to_date_toast: bool = False) -> None:
        local_version_str = importlib.metadata.version('rencher')

        try:
            response = requests.get('https://api.github.com/repos/danatationn/rencher/releases/latest')
        except requests.exceptions.ConnectionError:
            logging.error('Couldn\'t check upstream version!')
            return
        else:
            if response.status_code != 200:
                logging.error(f'Unexpected status code while checking upstream version: {response.status_code}')
                return

            data = cast(GitHubRelease, response.json())

            version_str = data['tag_name'].replace('v', '')
            upstream_version = tuple(map(int, version_str.split('.')))
            local_version = tuple(map(int, local_version_str.split('.')))

            toast = Adw.Toast(timeout=5)

            if upstream_version > local_version:
                if 'assets' in data and len(data['assets']) > 0 and 'html_url' in data:
                    download_url = data['html_url']
                else:
                    return

                logging.info(f'A new update is available! (v{version_str})')
                logging.info(download_url)
                toast.set_title(f'A new update is available! (v{version_str})')
                toast.set_button_label('Download')
                toast.connect('button-clicked', lambda *_: Gtk.show_uri(self.window, download_url, Gdk.CURRENT_TIME))

                GLib.idle_add(self.window.toast_overlay.add_toast, toast)
            elif upstream_version == local_version:
                toast.set_title(f"You're up to date! (v{local_version_str})")
            else:
                toast.set_title(f"You're bleeding-edge! (v{local_version_str})")
                self.window.add_css_class('devel')

            if show_up_to_date_toast:
                GLib.idle_add(self.window.toast_overlay.add_toast, toast)
            logging.info(toast.get_title())

class GitHubRelease(TypedDict):
    tag_name: str
    html_url: NotRequired[str]
    assets: NotRequired[list[dict[str, Any]]]
