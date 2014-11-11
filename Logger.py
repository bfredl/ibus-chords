from os.path import expanduser
import time
import os
import sys
import json
from subprocess import Popen, PIPE
logpath = expanduser("~/logs")

class DummyLogger(object):
    def __init__(self, *a):
        pass

    def __call__(self, *ev):
        event = [time.time()] + list(ev)
        if "KEYDEBUG" in os.environ:
            sys.stderr.write(json.dumps(event) + "\n")

class Logger(DummyLogger):
    def __init__(self, name):
        timet = time.strftime('%Y%m%d_%H%M%S')
        os.makedirs(logpath, exist_ok=True)
        fn = os.path.join(logpath, name + '_' + timet + '.gz')
         
        f = open(fn,'w')

        # ensure data is flushed on SIGTERM on this progess
        # (could probably be done with gzip.open but whatever)
        self._gzip = Popen(['gzip'], stdin=PIPE, stdout=f, bufsize=0)
        self.f = self._gzip.stdin

        self.name = name

    def __call__(self, *ev):
        event = [time.time(), self.name] + list(ev)
        self.f.write((json.dumps(event) + '\n').encode('utf8'))
        super().__call__(*ev)

    def close(self):
            self.f.close()


