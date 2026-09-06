import asyncio
import logging
import threading
from typing import Any

from pypresence.presence import AioPresence
from pypresence.exceptions import DiscordNotFound

TIMEOUT_SECS = 1

# TODO when discord isn't open this does some really nasty spam to the console. make it not do that

class Rpc:
    """
        rpc helper class

        handles cases where discord restarts, or when rpc is turned off and turned on again
    """
    client_id: int
    _presence: AioPresence | None
    _running: bool

    _current_state: dict[str, Any] | None
    _state_changed: bool

    _thread: threading.Thread | None
    _loop: asyncio.AbstractEventLoop | None

    def __init__(self, client_id: int):
        self.client_id = client_id
        self._presence = None
        self._running = False

        self._current_state = None
        self._state_changed = False

        self._thread = None
        self._loop = None


    async def _connect(self) -> bool:
        try:
            self._presence = AioPresence(self.client_id)
            await self._presence.connect()
            logging.info('RPC connected')
            return True
        except DiscordNotFound:
            # TODO make it so it prints the error once . use the variables above
            return False
        except Exception as e:
            self._presence = None
            logging.error(e)
            return False

    async def _run_loop(self):
        """ loop that checks if the rpc is connected and if it is, it updates it only when the state changes """
        while self._running:
            if await self._connect():
                self._current_state = None
                self._state_changed = False
                try:
                    while self._running and self._presence:
                        await asyncio.sleep(TIMEOUT_SECS)
                        if self._state_changed:
                            if self._current_state:
                                await self._presence.update(**self._current_state)
                            elif not self._current_state:
                                await self._presence.clear()
                            logging.debug(f'RPC updated ({self._current_state})')
                            self._state_changed = False
                except Exception:
                    pass

            if self._running:
                await asyncio.sleep(TIMEOUT_SECS)

    def _start_loop(self):
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._run_loop())

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._start_loop, daemon=True)
        self._thread.start()

    def update(self, **kwargs) -> None:

        if kwargs != self._current_state:
            self._current_state = kwargs
            self._state_changed = True

    def clear(self) -> None:
        if self._current_state is not None:
            self._current_state = None
            self._state_changed = True

    def stop(self) -> None:
        self._running = False
        self._current_state = None
        self._presence = None
