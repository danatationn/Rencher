import os.path
from collections.abc import Iterable
from configparser import ConfigParser
from pathlib import Path
from typing import TYPE_CHECKING, override

from rencher.renpy.paths import config_path, local_path

if TYPE_CHECKING:
    from _typeshed import StrOrBytesPath, SupportsWrite


class GameConfig:
    __config: ConfigParser
    game_config_path: Path
    structure: dict[str, dict[str, str | float]] = {
        'info': {
            'nickname': '',     # str
            'last_played': 0.0, # float
            'playtime': 0.0,    # float
            'added_on': 0.0,    # float
            'codename': '',     # str
        },
        'options': {
            'skip_splash_scr': '',  # bool
            'skip_main_menu': '',   # bool
            'forced_save_dir': '',  # bool
            'discord_rpc': '',      # bool
            # 'save_slot': 1,
        },
        'overwritten': {
            'skip_splash_scr': '',  # bool
            'skip_main_menu': '',   # bool
            'forced_save_dir': '',  # bool
            'discord_rpc': '',      # bool
        },
    }

    def __init__(self, game_config_path: Path | str):
        super().__init__()

        if isinstance(game_config_path, str):
            game_config_path = Path(game_config_path)

        self.__config = ConfigParser()
        self.game_config_path = Path(game_config_path)
        self.read(game_config_path)

    def read(self, config_path: Path | None = None, encoding: str | None = None) -> list[str]:
        if not config_path:
            config_path = self.game_config_path

        read_ok = self.__config.read(config_path, encoding)
        self.validate()
        return read_ok

    def validate(self):
        rencher_config = RencherConfig()

        for section, keys in self.structure.items():
            if section not in self.__config:
                self.__config.add_section(section)

            for key, value in keys.items():
                if key not in self.__config[section]:
                    self.__config[section][key] = str(value)

                # if value and self.__config[section][key]:
                if isinstance(value, bool):
                    value = self.__config.getboolean(section, key, fallback='')
                elif isinstance(value, int):
                    value = self.__config.getint(section, key, fallback=value)
                elif isinstance(value, float):
                    value = self.__config.getfloat(section, key, fallback=value)
                else:
                    value = ''

                self.__config[section][key] = str(value)

        for key, _ in self.structure['overwritten'].items():
            if self.__config['options'][key]:
                self.__config['overwritten'][key] = self.__config['options'][key]
            else:
                self.__config['overwritten'][key] = rencher_config['settings'][key]

    def write(self, fp: 'SupportsWrite[str] | None' = None, space_around_delimiters: bool = True):
        new_config = ConfigParser()
        for section in ['info', 'options']:
            new_config.add_section(section)
            for key, values in self.__config[section].items():
                new_config[section][key] = values

        game_config_dir = self.game_config_path.parent
        game_config_dir.mkdir(parents=True, exist_ok=True)
        open(self.game_config_path, 'a').close()
        if not fp:
            fp = open(self.game_config_path, 'w')
        new_config.write(fp, space_around_delimiters)
        fp.close()

    def get_value(self, key: str, overwritten: bool = False) -> str | float | bool | None:
        if key in self.__config['info']:
            try:
                return self.__config['info'].getfloat(key)
            except ValueError:
                return self.__config['info'][key]

        if key in self.__config['options']:
            if key in self.structure['overwritten'].keys() and overwritten:
                value = self.__config['overwritten'][key]
            else:
                try:
                    value = self.__config['options'].getint(key)
                except ValueError:
                    value = self.__config['options'][key]

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
