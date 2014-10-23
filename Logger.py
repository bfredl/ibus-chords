from os.path import expanduser
import time
import os
import json
logpath = expanduser("~/logs")

class DummyLogger(object):
    def __init__(self, *a):
        pass

    def __call__(self, *a):
        pass


class Logger(object):
    def __init__(self, name):
        timet = time.strftime('%Y%m%d_%H%M%S')
        os.makedirs(logpath, exist_ok=True)
        fn = os.path.join(logpath, name + '_' + timet)
        self.f = open(fn,'w')
        self.name = name

    def __call__(self, *ev):
        event = [time.time(), self.name] + list(ev)
        self.f.write(json.dumps(event) + '\n')


