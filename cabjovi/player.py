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
import subprocess

_logger = logging.getLogger(__name__)


# Manages mpg123 subprocess for MP3 playback.
class Player:
    def __init__(self, alsa_device='hw:1,0'):
        self._alsa_device = alsa_device
        self._process = None
        self._cur_file_path = None

    # Starts playing an MP3 file `file_path`.
    #
    # Returns `True` if playback started successfully.
    def play(self, file_path):
        self.stop()

        try:
            _logger.info(f'Starting mpg123 process to play `{file_path}`...')

            self._process = subprocess.Popen(
                ['mpg123', '-q', '-a', self._alsa_device, str(file_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self._cur_file_path = file_path
            _logger.info(f'Playing `{file_path.name}`...')
            return True
        except Exception as exc:
            _logger.error(f'Failed to start mpg123: {exc}')
            self._process = None
            self._cur_file_path = None
            return False

    # Terminates the mpg123 process without waiting.
    def terminate(self):
        if self._process is not None:
            try:
                _logger.info(f'Terminating mpg123 process...')
                self._process.terminate()
            except Exception:
                pass

    # Stops current playback.
    def stop(self):
        if self._process is not None:
            _logger.info(f'Terminating mpg123 process...')

            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _logger.warning(f'Failed to terminate mpg123 ({exc}); killing it...')
                self._process.kill()
                self._process.wait()
            except Exception as exc:
                _logger.warning(f'Error stopping mpg123: {exc}')
            finally:
                self._process = None
                self._cur_file_path = None

    # Waits for the current track to finish.
    def wait(self):
        if self._process is not None:
            self._process.wait()
