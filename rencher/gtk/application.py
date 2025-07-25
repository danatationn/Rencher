import logging
import os
import sys
import threading

import gi
import requests
from watchdog.observers import Observer

import rencher
from rencher import local_path
from rencher.renpy.config import RencherConfig

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

Adw.init()

from rencher.gtk.filemonitor import RencherFileMonitor  # noqa: E402
from rencher.gtk.window import RencherWindow  # noqa: E402


class RencherApplication(Gtk.Application):
    config: dict = None
    window: RencherWindow = None
    file_monitor: RencherFileMonitor = None

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, **kwargs,
            application_id='com.github.danatationn.rencher',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )

        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Enable verbose output')
        self.add_main_option('version', ord('V'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE, 'Prints version')
        self.add_main_option('data-dir', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.STRING, 'Forces a data directory')

        logging.basicConfig(
            level=logging.INFO,
            format='[%(levelname)s\t%(asctime)s.%(msecs)-3d %(module)-16s] %(message)s',
            datefmt='%H:%M:%S', 
        )

        watchdog_logger = logging.getLogger('watchdog')
        watchdog_logger.propagate = False
        urllib3_logger = logging.getLogger('urllib3')
        urllib3_logger.setLevel(logging.WARNING)
        

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        
        if options.contains('verbose'):
            logging.getLogger().setLevel(logging.DEBUG)
        if options.contains('version'):
            print(rencher.__version__)
            return 0
        if options.contains('data-dir'):
            data_dir = options.lookup_value('data-dir').get_string()
            logging.info(f'Setting data directory at {os.path.abspath(data_dir)}')
            
        self.activate()
        return 0
    
    def do_activate(self):
        Gtk.Application.do_activate(self)

        self.config = RencherConfig()
        self.window = RencherWindow(application=self)
        self.window.present()
        self.file_monitor = RencherFileMonitor(self.window)

        version_thread = threading.Thread(target=self.check_version)
        version_thread.run()

    def check_version(self) -> tuple[str] | None:
        if getattr(sys, 'frozen', False):
            return
        if self.config['settings']['suppress_updates'] == 'true':
            return

        try:
            response = requests.get('https://api.github.com/repos/danatationn/rencher/releases/latest')
        except requests.exceptions.ConnectionError:
            return
        else:
            if response.status_code == 404:
                return
            version = response.json()['tag_name'].replace('v', '')

            if version > rencher.__version__:
                if 'assets' in response.json() and len(response.json()['assets']) > 0:
                    download_url = response.json()['html_url']
                else:
                    return

                logging.info(f'A new update is available! (v{version})')
                logging.info(download_url)
                toast = Adw.Toast(
                    title=f'A new update is available! (v{version})',
                    timeout=5,
                    button_label='Download',
                )
                toast.connect('button-clicked', lambda *_: (
                    Gtk.show_uri(self.window, download_url, Gdk.CURRENT_TIME)
                ))

                self.window.toast_overlay.add_toast(toast)
            else:
                logging.info(f'You\'re up to date! (v{rencher.__version__})')
