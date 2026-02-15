# Copyright © 2026 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging
import threading
import time

import alsaaudio
import gpiod

_logger = logging.getLogger(__name__)


# ALSA mixer control for muting/unmuting.
class AlsaMixer:
    def __init__(self, card_name: str, mixer_name: str) -> None:
        self._mixer: alsaaudio.Mixer | None = None
        self._card_index: int | None = None

        try:
            cards = alsaaudio.cards()

            for i, card in enumerate(cards):
                if card_name in card:
                    _logger.info(f'Found ALSA card `{card}` at index #{i}')
                    self._card_index = i
                    self._mixer = alsaaudio.Mixer(mixer_name, cardindex=i)
                    _logger.info(f'Connected to ALSA mixer `{mixer_name}` on card #{i}')
                    return

            _logger.warning(f'No ALSA card matching `{card_name}` found')
        except Exception as exc:
            _logger.warning(f'Failed to initialize ALSA mixer: {exc}')

    @property
    def card_index(self) -> int | None:
        return self._card_index

    # Mutes the mixer, returning `True` on success.
    def mute(self) -> bool:
        if self._mixer is None:
            return False

        try:
            self._mixer.setmute(1)
            _logger.info('Muted!')
            return True
        except Exception as exc:
            _logger.error(f'Failed to mute: {exc}')
            return False

    # Unmutes the mixer, returning `True` on success.
    def unmute(self) -> bool:
        if self._mixer is None:
            return False

        try:
            self._mixer.setmute(0)
            _logger.info('Unmuted!')
            return True
        except Exception as exc:
            _logger.error(f'Failed to unmute: {exc}')
            return False


# GPIO-based mute control with debounce and auto-mute timeout.
class MuteCtrl:
    def __init__(self, mixer: AlsaMixer, gpio_chip_dev: str, gpio_pin: int,
                 switch_debounce: float, door_debounce: float,
                 auto_mute_delay: float) -> None:
        self._mixer = mixer
        self._gpio_chip_dev = gpio_chip_dev
        self._gpio_pin = gpio_pin
        self._switch_debounce = switch_debounce
        self._door_debounce = door_debounce
        self._auto_mute_delay = auto_mute_delay
        self._last_gpio_value: gpiod.line.Value | None = None
        self._is_muted = True
        self._last_mute_time: float = 0
        self._last_unmute_time: float = 0
        self._last_event_time: float = 0
        self._gpio_request: gpiod.LineRequest | None = None
        self._is_running = False
        self._gpio_thread: threading.Thread | None = None
        self._auto_mute_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def is_muted(self) -> bool:
        with self._lock:
            return self._is_muted

    # Performs muting operation.
    def _do_mute(self) -> None:
        with self._lock:
            if self._is_muted:
                return

            _logger.info('Muting...')

            if not self._mixer.mute():
                _logger.error('Mute failed; not updating internal state')
                return

            self._is_muted = True
            self._last_mute_time = time.time()

    # Performs unmuting operation.
    def _do_unmute(self) -> None:
        with self._lock:
            if not self._is_muted:
                return

            # The cabinet door itself (not the switch) may bounce back
            # when closed: wait for `self._door_debounce` before
            # allowing unmuting.
            if time.time() - self._last_mute_time < self._door_debounce:
                _logger.info('Ignoring unmute (lockout)')
                return

            _logger.info('Unmuting...')

            if not self._mixer.unmute():
                _logger.error('Unmute failed; not updating internal state')
                return

            self._is_muted = False
            self._last_unmute_time = time.time()

    # Background thread that polls for GPIO events.
    def _gpio_loop(self) -> None:
        assert self._gpio_request is not None

        while self._is_running:
            if not self._gpio_request.wait_edge_events(timeout=0.5):
                continue

            # Drain all pending events
            self._gpio_request.read_edge_events()

            # Wait for bounce to settle
            time.sleep(self._switch_debounce)

            # Drain any events that occurred during debounce
            while self._gpio_request.wait_edge_events(timeout=0):
                self._gpio_request.read_edge_events()

            # Read actual stable value
            val = self._gpio_request.get_value(self._gpio_pin)

            if val == self._last_gpio_value:
                # Value didn't change; ignore spurious edge event
                continue

            self._last_gpio_value = val
            _logger.info(f'GPIO value changed to {val}')

            if val == gpiod.line.Value.INACTIVE:
                self._do_mute()
            else:
                self._do_unmute()

    # Background thread that handles auto-mute timeout.
    def _auto_mute_loop(self) -> None:
        _logger.info('Auto-mute thread started')

        while self._is_running:
            time.sleep(1)

            with self._lock:
                if self._is_muted:
                    continue

                if (time.time() - self._last_unmute_time) >= self._auto_mute_delay:
                    _logger.info(f'Auto-mute triggered after {self._auto_mute_delay} seconds')

                    if self._mixer.mute():
                        self._is_muted = True
                        self._last_mute_time = time.time()
                    else:
                        _logger.error('Auto-mute failed; will retry')

    # Starts the mute controller.
    def start(self) -> None:
        if self._is_running:
            return

        self._is_running = True

        # Set up GPIO
        try:
            _logger.info(f'Requesting GPIO line #{self._gpio_pin} on `{self._gpio_chip_dev}`...')

            self._gpio_request = gpiod.request_lines(self._gpio_chip_dev,
                                                     consumer="cabjovi",
                                                     config={
                self._gpio_pin: gpiod.LineSettings(edge_detection=gpiod.line.Edge.BOTH,
                                                   bias=gpiod.line.Bias.PULL_UP)
            })

            _logger.info(f'GPIO mute control initialized on pin #{self._gpio_pin}')

            # Always start muted
            if self._mixer.mute():
                self._is_muted = True
                self._last_mute_time = time.time()
            else:
                _logger.error('Initial mute failed')

            # Start GPIO polling thread
            _logger.info('Starting GPIO polling thread...')
            self._gpio_thread = threading.Thread(target=self._gpio_loop, daemon=True)
            self._gpio_thread.start()
        except Exception as exc:
            _logger.warning(f'Failed to initialize GPIO: {exc}')
            # Default to muted if GPIO fails
            if self._mixer.mute():
                self._is_muted = True
                self._last_mute_time = time.time()

        # Start auto-mute thread
        _logger.info('Starting auto-mute thread...')
        self._auto_mute_thread = threading.Thread(target=self._auto_mute_loop, daemon=True)
        self._auto_mute_thread.start()

    # Stops the mute controller.
    def stop(self) -> None:
        self._is_running = False

        if self._gpio_thread is not None:
            _logger.info('Stopping GPIO polling thread...')
            self._gpio_thread.join(timeout=2)
            self._gpio_thread = None

        if self._gpio_request is not None:
            self._gpio_request.release()
            self._gpio_request = None

        if self._auto_mute_thread is not None:
            _logger.info('Stopping auto-mute thread...')
            self._auto_mute_thread.join(timeout=2)
            self._auto_mute_thread = None
