# -*- coding: utf-8 -
#
# This file is part of gunicorn released under the MIT license.
# See the NOTICE for more information.

import os
import os.path
import re
import sys
import time
import threading


class Reloader(threading.Thread):
    def __init__(self, extra_files=None, interval=1, callback=None):
        super(Reloader, self).__init__()
        self.setDaemon(True)
        self._extra_files = set(extra_files or ())
        self._extra_files_lock = threading.RLock()
        self._interval = interval
        self._callback = callback

    def add_extra_file(self, filename):
        with self._extra_files_lock:
            self._extra_files.add(filename)

    def get_files(self):
        fnames = [
            re.sub('py[co]$', 'py', module.__file__)
            for module in list(sys.modules.values())
            if hasattr(module, '__file__')
        ]

        with self._extra_files_lock:
            fnames.extend(self._extra_files)

        return fnames

    def run(self):
        mtimes = {}
        while True:
            for filename in self.get_files():
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    continue
                old_time = mtimes.get(filename)
                if old_time is None:
                    mtimes[filename] = mtime
                    continue
                elif mtime > old_time:
                    if self._callback:
                        self._callback(filename)
            time.sleep(self._interval)

try:
    from inotify.adapters import Inotify
    has_inotify = True
except ImportError:
    has_inotify = False


if has_inotify:

    class InotifyReloader(threading.Thread):
        valid_events = set((
            'IN_CREATE', 'IN_DELETE', 'IN_DELETE_SELF',
            'IN_MODIFY', 'IN_MOVE_SELF', 'IN_MOVED_FROM',
            'IN_MOVED_TO'))
        
        def __init__(self, extra_files=None, callback=None):
            super(InotifyReloader, self).__init__()
            self._callback = callback
            self._dirs = set()
            self._watcher = Inotify()

        def add_extra_file(self, filename):
            dirname = os.path.dirname(filename)

            if dirname in self._dirs:
                return

            self._watcher.add_watch(dirname)
            self._dirs.add(dirname)

        def get_dirs(self):
            fnames = [
                module.__file__
                for module in list(sys.modules.values())
                if hasattr(module, '__file__')
            ]

            fnames = [
                os.path.dirname(re.sub('py[co]$', 'py', module.__file__))
                for module in list(sys.modules.values())
                if hasattr(module, '__file__')
            ]

            return set(fnames)

        def run(self):
            self._dirs = self.get_dirs()
            print(self._dirs)
            for dirname in self._dirs:
                self._watcher.add_watch(dirname)

            for event in self._watcher.event_gen():
                if event is None:
                    continue
                
                types = event[1]
                filename = event[3]

                if len(set(types).intersection(self.valid_events)) == 0:
                    continue

                self._callback(filename)


