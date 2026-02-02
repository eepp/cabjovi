# Copyright © 2026 Philippe Proulx <eepp.ca>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# “Software”), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import logging
import signal
import sys
import time
from pathlib import Path

import typer

import cabjovi.mute
import cabjovi.playback
import cabjovi.player

# Graceful shutdown state
_shutdown_requested = False
_player = None


# Configures logging for the service.
def _setup_logging():
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])


# Handles shutdown signals.
def _sig_handler(signum, frame):
    global _shutdown_requested

    _shutdown_requested = True
    logging.info(f'Received signal {signum}: shutting down...')

    if _player is not None:
        _player.terminate()


app = typer.Typer()


@app.command()
def main(
    base_dir: Path = typer.Argument(...,
                                    help='Base directory containing time-scheduled music directories',
                                    exists=True, file_okay=False,
                                    dir_okay=True, resolve_path=True),
    alsa_card_name: str = typer.Option('default', '--alsa-card', '-c',
                                       help='ALSA card name'),
    alsa_mixer_name: str = typer.Option('default', '--alsa-mixer', '-m',
                                        help='ALSA mixer control name'),
    gpio_chip_dev: str = typer.Option('/dev/gpiochip0', '--gpio-chip-dev',
                                      help='GPIO chip device'),
    gpio_pin: int = typer.Option(3, '--gpio-pin', '-g',
                                 help='GPIO pin for mute control: short with ground to mute'),
    switch_debounce: float = typer.Option(0.05, '--switch-debounce',
                                          help='Switch debounce delay (s)'),
    door_debounce: float = typer.Option(1.0, '--door-debounce',
                                        help='Door debounce delay (s) (unmute lockout after mute)'),
    auto_mute_delay: float = typer.Option(300.0, '--auto-mute-delay',
                                          help='Auto-mute delay (s)'),
    poll_interval: float = typer.Option(10.0, '--poll-interval', '-p',
                                        help='Polling interval (s) when no directory matches'),
):
    # Set up logging
    _setup_logging()
    logger = logging.getLogger('cabjovi')
    logger.info(f'Starting cabjovi with base directory `{base_dir}`')

    # Set up signal handlers
    signal.signal(signal.SIGTERM, _sig_handler)
    signal.signal(signal.SIGINT, _sig_handler)

    global _player

    # Initialize components
    mixer = cabjovi.mute.AlsaMixer(alsa_card_name, alsa_mixer_name)
    mute_ctrl = cabjovi.mute.MuteCtrl(mixer, gpio_chip_dev, gpio_pin,
                                      switch_debounce, door_debounce, auto_mute_delay)
    alsa_device = f'hw:{mixer.card_index},0' if mixer.card_index is not None else 'default'
    _player = cabjovi.player.Player(alsa_device)
    playback = cabjovi.playback.PlaybackCtrl(base_dir)

    # Start mute controller (starts the auto-mute thread)
    mute_ctrl.start()

    try:
        while not _shutdown_requested:
            next_mp3_file_path = playback.select_next()

            if next_mp3_file_path is None:
                _player.stop()
                time.sleep(poll_interval)
                continue

            if _player.play(next_mp3_file_path):
                _player.wait()
            else:
                logger.error(f'Failed to play `{next_mp3_file_path.name}`; retrying in 2 seconds...')
                time.sleep(2)
    except Exception as exc:
        logger.exception(f'Unexpected error in main loop: {exc}')
    finally:
        logger.info('Shutting down...')
        _player.stop()
        mute_ctrl.stop()
        logger.info('Chow les caves!')
