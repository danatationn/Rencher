import logging
import subprocess
from typing import override

from gi.repository import GLib, GObject

from rencher.renpy.config import GameConfig
from rencher.renpy.game import Game


def format_date(time: float) -> str | None:
    date = GLib.DateTime.new_from_unix_local(int(time))
    now = GLib.DateTime.new_now_local()
    if not date or not now:
        return None
    today = GLib.DateTime.new_local(now.get_year(), now.get_month(), now.get_day_of_month(), 0, 0, 0)
    if not today:
        return None
    yesterday = today.add_days(-1)
    tomorrow = today.add_days(1)
    if not yesterday or not tomorrow:
        return None

    if date.to_unix() == 0:
        return None
    elif date.compare(tomorrow) >= 0:
        return date.format('In the future')
    elif date.compare(today) >= 0:
        return date.format('Today, %I:%M %p')
    elif date.compare(yesterday) >= 0:
        return date.format('Yesterday, %I:%M %p')
    else:
        return date.format('%d %b %Y, %I:%M %p')

def format_playtime(time: float) -> str | None:
    hours = int(time / 3600)
    minutes = int((time % 3600) / 60)
    seconds = int((time % 3600) % 60)

    formatted_playtime = f'{hours:02}:{minutes:02}:{seconds:02}'
    if formatted_playtime != '00:00:00':
        return formatted_playtime
    else:
        return None

class GameEntry(GObject.Object):
    __gtype_name__: str = 'GameEntry'
    _game: Game
    _process: subprocess.Popen[bytes] | None
    name: GObject.Property = GObject.Property(type=str, default='N/A')
    rpath: GObject.Property = GObject.Property(type=str, default='N/A')
    apath: GObject.Property = GObject.Property(type=str, default='N/A')
    last_played: GObject.Property = GObject.Property(type=str, default='Never')
    playtime: GObject.Property = GObject.Property(type=str, default='N/A')
    added_on: GObject.Property = GObject.Property(type=str, default='N/A')
    version: GObject.Property = GObject.Property(type=str, default='N/A')
    codename: GObject.Property = GObject.Property(type=str, default='N/A')

    def __init__(self, rpath: str | None = None, game: Game | None = None):
        super().__init__()

        self._process = None

        if not rpath and not game:
            return
        if game and not rpath:
            rpath = str(game.rpath)
        if rpath and not game:
            game = Game(rpath=rpath)

        if game:
            self._game = game
            self.refresh(game)

    @override
    def __eq__(self, other: object):
        if isinstance(other, GameEntry):
            return self.rpath == other.rpath
        else:
            return False

    @override
    def __hash__(self):
        return hash(self.rpath)

    def run(self) -> subprocess.Popen[bytes]:
        process = self.game.run()
        self._process = process
        return process

    def refresh(self, game: Game) -> None:
        game.config.read()

        property_map: dict[str, object] = {
            'name': lambda: game.name,
            'rpath': lambda: game.rpath,
            'apath': lambda: game.apath,
            'last_played': lambda: game.config.get_value('last_played'),
            'added_on': lambda: game.config.get_value('added_on'),
            'playtime': lambda: game.config.get_value('playtime'),
            'version': lambda: '.'.join(str(i) for i in game.get_renpy_version() or []),
            'codename': lambda: game.codename,
        }

        for prop, getter in property_map.items():
            try:
                value = getter()  # pyright: ignore[reportCallIssue, reportUnknownVariableType]
                if prop in ['last_played', 'added_on']:
                    value = format_date(value)
                elif prop == 'playtime':
                    value = format_playtime(value)

                setattr(self, prop, value if value else 'N/A')
            except Exception as e:
                setattr(self, prop, 'Error!')
                logging.warning(f'Couldn\'t set {prop}. {e}')

    # i need to add all the other properties

    @property
    def game(self) -> Game:
        return self._game
    @game.setter
    def game(self, value: Game) -> None:
        self._game = value
        self.refresh(value)
    @property
    def is_mod(self) -> bool | None:
        return self._game.is_mod
    @property
    def is_valid(self) -> bool | None:
        return self._game.is_valid
    @property
    def is_launchable(self) -> bool | None:
        return self._game.is_launchable
    @property
    def process(self) -> subprocess.Popen[bytes] | None:
        return self._process
    @property
    def config(self) -> GameConfig:
        return self.game.config
