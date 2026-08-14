import asyncio
import logging
import os.path
from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Gio, GObject, Gtk

from rencher.gtk.game_entry import GameEntry
from rencher.renpy.config import RencherConfig
from rencher.renpy.game import GameInvalidError, GameNoExecutableError

if TYPE_CHECKING:
    from rencher.gtk.window import MainWindow


class Library(GObject.Object):
    window: 'MainWindow'
    store: Gio.ListStore

    __gsignals__: dict[str, tuple[GObject.SignalFlags, None, tuple[object]]] = {
        'game-added': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
        'game-removed': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
        'game-changed': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
    }

    def __init__(self, window: 'MainWindow'):
        super().__init__()
        self.window = window
        self.store = Gio.ListStore(item_type=GameEntry)

    def find(self, rpath: str | Path) -> tuple[int, GameEntry] | None:
        rpath = os.path.normpath(rpath)
        for item in self.store:
            if not item:
                continue
            item_rpath = os.path.normpath(item.rpath)
            if rpath == item_rpath or rpath.startswith(item_rpath + os.sep):
                found, pos = self.store.find(item)
                if found:
                    # logging.debug(f'{rpath} belongs to {item.rpath}')
                    return pos, item
        return None

    def find_row(self, row: Gtk.ListBoxRow) -> GameEntry | None:
        for item in self.store:
            if not item:
                continue
            if item.row == row:
                return item

    def load_games(self) -> None:
        data_dir = RencherConfig().get_data_dir()
        games_dir = Path(data_dir) / 'games'
        games_dir.mkdir(exist_ok=True, parents=True)
        for item in list(self.store):
            if isinstance(item, GameEntry):
                self.remove_game(item.rpath)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        for d in games_dir.iterdir():
            rpath = os.path.join(games_dir, d)
            loop.run_in_executor(None, self.add_game, rpath)

    def add_game(self, rpath: str) -> None:
        if self.find(rpath):
            self.change_game(rpath)
            return

        try:
            game_item = GameEntry(rpath=rpath)
        except GameNoExecutableError:
            self.window.codename_dialog.popup(rpath)
        except GameInvalidError:
            logging.debug(f'Couldn\'t load {rpath}')
        else:
            self.store.append(game_item)
            self.emit('game-added', game_item)
        logging.debug(f'Added: "{os.path.basename(rpath)}"')

    def remove_game(self, rpath: str) -> None:
        result = self.find(rpath)
        if result:
            i, item = result
            self.store.remove(i)
            self.emit('game-removed', item)
        logging.debug(f'Removed: "{os.path.basename(rpath)}"')

    def change_game(self, rpath: str) -> None:
        result = self.find(rpath)
        if result:
            i, game_item = result
            game_item.refresh(game_item.game)
            self.store.items_changed(i, 1, 1)
            self.emit('game-changed', game_item)
        logging.debug(f'Changed: "{os.path.basename(rpath)}"')
