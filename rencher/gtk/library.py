import logging
import os.path
from pathlib import Path
from typing import TYPE_CHECKING

from gi.repository import Gio, GLib, GObject

from rencher.gtk.game_entry import GameEntry
from rencher.gtk.tasks import DeleteGameTask, ImportGameTask, RencherTask
from rencher.renpy.config import RencherConfig
from rencher.renpy.game import Game, GameInvalidError, GameNoExecutableError

if TYPE_CHECKING:
    from rencher.gtk.window import MainWindow


class Library(GObject.Object):
    window: 'MainWindow'
    store: Gio.ListStore

    # signal name: flags, return types, arg types
    __gsignals__: dict[str, tuple[GObject.SignalFlags, None, tuple[type, ...]]] = {
        'game-added': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
        'game-removed': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
        'game-changed': (GObject.SignalFlags.RUN_FIRST, None, (GameEntry,)),
        'task-started': (GObject.SignalFlags.RUN_FIRST, None, (RencherTask, object)),
        'task-finished': (GObject.SignalFlags.RUN_FIRST, None, (RencherTask, object)),
        'message': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, window: 'MainWindow'):
        super().__init__()
        self.window = window
        self.store = Gio.ListStore(item_type=GameEntry)

        action_group = Gio.SimpleActionGroup.new()
        # s = apath
        delete_action = Gio.SimpleAction.new_stateful('delete-game', GLib.VariantType.new('s'), GLib.Variant('d', 0.0))
        delete_action.connect('activate', self.delete_game)
        # sss = rpath, nickname, game rpath
        import_action = Gio.SimpleAction.new_stateful('import-game', GLib.VariantType('(sss)'), GLib.Variant('d', 0.0))
        import_action.connect('activate', self.import_game)

        action_group.add_action(delete_action)
        action_group.add_action(import_action)

        self.window.insert_action_group('library', action_group)

    def find(self, rpath: str | Path) -> tuple[int, GameEntry] | None:
        rpath = os.path.normpath(rpath)
        for entry in self.store:
            if not entry or not isinstance(entry, GameEntry):
                continue
            item_rpath = os.path.normpath(entry.rpath)
            if rpath == item_rpath or rpath.startswith(item_rpath + os.sep):
                found, pos = self.store.find(entry)
                if found:
                    return pos, entry
        return None

    def load_games(self) -> None:
        data_dir = RencherConfig().get_data_dir()
        games_dir = Path(data_dir) / 'games'
        games_dir.mkdir(exist_ok=True, parents=True)
        logging.info(f'Loading games from "{data_dir}"')
        for item in list(self.store):
            if isinstance(item, GameEntry):
                self.remove_game(item.rpath)

        for dir in games_dir.iterdir():
            rpath = games_dir / dir
            GLib.idle_add(self.add_game, rpath)

    def _msg(self, _t: RencherTask, text: str):
        self.emit('message', text)

    def add_game(self, rpath: str) -> None:
        if self.find(rpath):
            self.update_game(rpath)
            return

        try:
            game_item = GameEntry(rpath=rpath)
        except GameNoExecutableError:
            self.window.codename_dialog.popup(rpath)
        except GameInvalidError:
            logging.warning(f'Couldn\'t load "{os.path.basename(rpath)}"')
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

    def update_game(self, rpath: str) -> None:
        result = self.find(rpath)
        if result:
            i, game_item = result
            game_item.update(game_item.game)
            self.store.items_changed(i, 1, 1)
            self.emit('game-changed', game_item)
        logging.debug(f'Changed: "{os.path.basename(rpath)}"')

    def delete_game(self, _action: Gio.SimpleAction, parameter: GLib.Variant) -> None:
        rpath = parameter.get_string()
        task = DeleteGameTask(rpath)
        if result := self.find(rpath):
            self.emit('task-started', task, result[1])

        def _on_finished(t: DeleteGameTask, _p: GObject.ParamSpec):
            try:
                game = Game(rpath)
                if not game.validate():
                    self.remove_game(rpath)
            except Exception:
                self.remove_game(rpath)
            self.emit('task-finished', t, None)

        task.connect('message', self._msg)
        task.connect('notify::finished', _on_finished)
        task.start()

    def import_game(self, _action: Gio.SimpleAction, parameter: GLib.Variant) -> None:
        file_path = parameter.get_child_value(0).get_string()
        nickname = parameter.get_child_value(1).get_string()
        nickname = nickname if nickname != '' else None
        game_rpath = parameter.get_child_value(2).get_string()

        target_entry = self.find(game_rpath)
        task = ImportGameTask(Path(file_path), nickname, target_entry[1] if target_entry else None)

        self.emit('task-started', task, None)

        def _on_finished(t: ImportGameTask, _p: GObject.ParamSpec):
            if t.game and t.game_path:
                entry = GameEntry(game=t.game)
                self.store.append(entry)
                self.update_game(str(t.game_path))
                self.emit('task-finished', t, entry)
            else:
                self.emit('task-finished', t, None)

        task.connect('message', self._msg)
        task.connect('notify::finished', _on_finished)
        task.start()
