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
import random

import cabjovi.sched

_logger = logging.getLogger(__name__)


# Controls random playback within time-scheduled directories.
class PlaybackCtrl:
    def __init__(self, base_dir):
        self._base_dir = base_dir
        self._cur_dir = None
        self._last_played_file_name = None

    # Lists all the MP3 files in `dir`, sorted alphabetically.
    @staticmethod
    def _list_mp3_files(dir):
        if not dir.is_dir():
            return []

        mp3_files = []

        for entry in dir.iterdir():
            if entry.is_file() and entry.suffix.lower() == '.mp3':
                mp3_files.append(entry)

        return sorted(mp3_files, key=lambda p: p.name.lower())

    # Selects the next MP3 file to play based on current time.
    #
    # Returns the next MP3 file to play, or `None` if nothing to
    # play (forced silence).
    def select_next(self):
        cur_dir = cabjovi.sched.get_cur_dir(self._base_dir)

        if cur_dir is None:
            _logger.info('No directory for current time')
            self._cur_dir = None
            self._last_played_file_name = None
            return

        file_paths = self._list_mp3_files(cur_dir)

        if not file_paths:
            _logger.info(f'Directory `{cur_dir}` has no files')
            self._cur_dir = cur_dir
            self._last_played_file_name = None
            return

        _logger.info(f'Directory `{cur_dir}` has {len(file_paths)} file(s)')

        if cur_dir != self._cur_dir:
            _logger.info(f'Directory changed to `{cur_dir}`')
            self._cur_dir = cur_dir
            self._last_played_file_name = None

        # Build candidate list, excluding last played file
        if self._last_played_file_name is not None and len(file_paths) > 1:
            candidates = [f for f in file_paths if f.name != self._last_played_file_name]
        else:
            candidates = file_paths

        selected_file_path = random.choice(candidates)
        self._last_played_file_name = selected_file_path.name
        _logger.info(f'Selected `{selected_file_path}` (random from {len(candidates)} candidate(s))')
        return selected_file_path
