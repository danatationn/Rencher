import os.path
import platform
import subprocess

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio  # noqa: E402


def open_file_manager(path: str):
    if platform.system() == 'Linux':
        Gio.AppInfo.launch_default_for_uri('file://' + path)
    elif platform.system() == 'Windows':
        subprocess.run(['explorer', path.replace('/', '\\')])

def windowficate_path(path: str) -> str:
    """
    returns a file that abides by the Windows file naming conventions

    Args:
        path (str): is used
    Returns:
        str: the new path
    """
    forbidden_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    forbidden_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8',
                       'COM9', 'COM¹', 'COM²', 'COM³', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8',
                       'LPT9', 'LPT¹', 'LPT²', 'LPT³']

    name = os.path.basename(path)
    new_name = ''
    for char in name:
        if char in forbidden_chars:
            new_name += '_'
        else:
            new_name += char
    if new_name in forbidden_names:
        new_name = 'game'

    parent = os.path.dirname(path)
    return os.path.join(parent, new_name)
