import os.path
from collections.abc import Iterable
from configparser import ConfigParser
from pathlib import Path
from typing import TYPE_CHECKING, override

from rencher.renpy.paths import config_path, local_path

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath, SupportsWrite


class GameConfig(ConfigParser):
    game_config_path: Path
    structure: dict[str, dict[str, str | float]] = {
        'info': {
            'nickname': '',
            'last_played': 0.0,
            'playtime': 0.0,
            'added_on': 0.0,
            'codename': '',
            # TODO 'is_mod': '',
        },
        'options': {
            'skip_splash_scr': '',
            'skip_main_menu': '',
            'forced_save_dir': '',
            'discord_rpc': '',
            # 'save_slot': 1,
        },
        'overwritten': {
            'skip_splash_scr': '',
            'skip_main_menu': '',
            'forced_save_dir': '',
            'discord_rpc': '',
        },
    }

    def __init__(self, game_config_path: Path | str):
        super().__init__()
        self.game_config_path = Path(game_config_path)
        self.read(game_config_path)

    @override
    def read(
        self, filenames: 'StrOrBytesPath | Iterable[StrOrBytesPath] | None' = None, encoding: str | None = None
    ) -> list[str]:
        if not filenames:
            filenames = self.game_config_path
        read_ok = super().read(filenames)
        self.validate()
        return read_ok

    def validate(self):
        rencher_config = RencherConfig()

        for section, keys in self.structure.items():
            if section not in self:
                self.add_section(section)

            for key, values in keys.items():
                if key not in self[section]:
                    self[section][key] = str(values)

                if values and self[section][key]:
                    if isinstance(values, bool):
                        value = self.getboolean(section, key, fallback='')
                    elif isinstance(values, int):
                        value = self.getint(section, key, fallback=values)
                    elif isinstance(values, float):
                        value = self.getfloat(section, key, fallback=values)
                    else:
                        value = ''

                    self[section][key] = str(value)

        for key, _ in self.structure['overwritten'].items():
            if self['options'][key]:
                self['overwritten'][key] = self['options'][key]
            else:
                self['overwritten'][key] = rencher_config['settings'][key]

    @override
    def write(self, fp: 'SupportsWrite[str] | None' = None, space_around_delimiters: bool = True):
        new_config = ConfigParser()
        for section in ['info', 'options']:
            new_config.add_section(section)
            for key, values in self[section].items():
                new_config[section][key] = values

        game_config_dir = self.game_config_path.parent
        game_config_dir.mkdir(parents=True, exist_ok=True)
        open(self.game_config_path, 'a').close()
        if not fp:
            fp = open(self.game_config_path, 'w')
        new_config.write(fp, space_around_delimiters)
        fp.close()

    def get_value(self, key: str, overwritten: bool = False) -> str | float | bool | None:
        if key in self['info']:
            try:
                return self['info'].getfloat(key)
            except ValueError:
                return self['info'][key]

        if key in self['options']:
            if key in self.structure['overwritten'].keys() and overwritten:
                value = self['overwritten'][key]
            else:
                try:
                    value = self['options'].getint(key)
                except ValueError:
                    value = self['options'][key]

            if value == 'true':
                return True
            elif value == 'false':
                return False
            else:
                return value
        return None


class RencherConfig(ConfigParser):
    def __init__(self):
        super().__init__()
        self.read()

    @override
    def read(
        self, filenames: 'StrOrBytesPath | Iterable[StrOrBytesPath] | None' = None, encoding: str | None = None
    ) -> list[str]:
        if not filenames:
            filenames = config_path
        read_ok = super().read(filenames)
        self.validate()
        return read_ok

    def validate(self) -> None:
        structure = {
            'settings': {
                'data_dir': '',
                'suppress_updates': 'false',
                'delete_on_import': 'false',
                'skip_splash_scr': 'false',
                'skip_main_menu': 'false',
                'forced_save_dir': 'false',
                'discord_rpc': 'false',
                'windowficate_filenames': 'true',
            },
        }

        for section, keys in structure.items():
            if section not in self:
                self.add_section(section)

            for key, values in keys.items():
                if key not in self[section]:
                    self[section][key] = values

        if not os.path.isfile(config_path):
            self.write()

    @override
    def write(self, fp: 'SupportsWrite[str] | None' = None, space_around_delimiters: bool = True) -> None:
        config_dir = Path(config_path).parent
        config_dir.mkdir(parents=True, exist_ok=True)

        open(config_path, 'a').close()
        if not fp:
            fp = open(config_path, 'w')
        super().write(fp, space_around_delimiters)
        fp.close()

    def get_data_dir(self) -> str:
        if self['settings']['data_dir'] == '':
            return str(local_path)
        else:
            return self['settings']['data_dir']
