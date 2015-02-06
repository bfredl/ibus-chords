# -*- coding: utf-8 -*-
from __future__ import print_function
from operator import or_
from collections import namedtuple, ChainMap
import os.path as path
import time
from keysym import desc_to_keysym, keysym_desc
import sys
from functools import reduce, partial
from itertools import chain, product
from types import SimpleNamespace
from Logger import *
from operator import or_
import zmq
import traceback

# keeps track of time distance to closest condition that will change
class Timevar:
    def __init__(self, value, src=None):
        self.value = value
        if src is None:
            self.src = self
            self.mindelta = sys.maxsize # \infty
            self.has_delta = False
        else:
            self.src = src

    def __sub__(self, other):
        return Timevar(self.value - other, self)

    def __add__(self, other):
        return Timevar(self.value + other, self)

    def __lt__(self, other):
        delta = other - self.value
        if delta > 0:
            self.src.mindelta = min([self.src.mindelta, delta])
            self.src.has_delta = True
            return True
        else:
            return False

    def __ge__(self, other):
        return not self.__lt__(other)

desc_table = {
        'Return': '↩',
        'BackSpace': '◄',
        # FIXME: these from the modmap
        'Control_L': 'C-',
        'Control_R': 'C-',
        'Escape': 'ESC',
        'Left': '',
        'Right': '',
        'Up': '',
        'Down': '',
        }

SHIFT = 0x01
CTRL = 0x04
ALT = 0x08
LEVEL3 = 0x80
HOLD = -1

dbg = False
def runfile(fname, glob):
    with open(fname, 'rb') as f:
        exec(compile(f.read(), fname, 'exec'), glob, glob)

Press = namedtuple('Press', ['keyval','keycode','state','time'])
Shift = namedtuple('Shift', ['base', 'hold'])
Command = namedtuple('Command', ['cmd', 'hold'])
def lookup(dct, val):
    return [k for k,v in dct.items() if v == val]
class KeyboardChorder(object):
    def __init__(self, im):
        self.im = im
        self.conf_file = path.expanduser('~/.config/chords')
        self.remap = ChainMap()
        self.logger = DummyLogger()
        self.real_logger = None
        self.configure()
        self.on_reset()
        self.quiet = False

        ctx = zmq.Context.instance()
        rtd = os.environ["XDG_RUNTIME_DIR"]
        self.sock = ctx.socket(zmq.PULL)
        self.sock.bind("ipc://{}/chords".format(rtd))
        fd = self.sock.getsockopt(zmq.FD)
        self.im.poll_read(fd, self.on_sock_poll)

    def lookup_keysym(self, s):
        if s == 'HOLD': return HOLD
        syms = self.im.lookup_keysym(s)
        return syms[0][0] if syms else s

    def translate_keymap(self, keymap):
        km = {}
        for desc, val in keymap.items():
            if isinstance(desc, str):
                chord = []
                for ch in desc:
                    if ch == 'F':
                        chord.append(lookup(self.modmap, LEVEL3))
                        chord.append((HOLD,))
                    else:
                        chord.append(lookup(self.unshifted, ch))
            elif isinstance(desc, Press):
                chord = [(desc.keycode,)]
            for ch in product(*chord):
                ch = tuple(sorted(ch))
                if isinstance(val, Shift):
                    if val.base is not None:
                        km[ch] = val.base
                    km[(HOLD,)+ch] = val.hold
                else:
                    km[ch] = val
        return km

    def configure(self):
        #FIXME: place these in a class w defaults
        def Sym(*a):
            mod = reduce(or_,a[:-1],0)
            keysym = desc_to_keysym(a[-1])
            keycode, state = self.im.lookup_keysym(keysym)[0]
            return Press(keysym, keycode, mod+state, 0)

        # Do you even curry?
        curry = partial(partial, partial)

        conf = SimpleNamespace(
            pause=self.pause,
            quiet=self.set_quiet,
            conf=self.configure,

            set_keymap=curry(self.set_keymap),
            lock=curry(self.toggle_lock),
            unlock=partial(self.set_lock, None),
            keymap={},
            parents={},
            Shift=Shift,
            Sym=Sym,
            SHIFT=0x01,
            CTRL=0x04,
            ALT=ALT,
            LEVEL3=0x80,
            on_reset=lambda: None,
            logs=False,
        )
        runfile(self.conf_file,conf.__dict__)
        self.holdThreshold = conf.holdThreshold
        self.holdThreshold2 = conf.holdThreshold2
        self.chordTreshold = conf.chordTreshold
        self.chordThreshold2 = conf.holdThreshold2
        self.modThreshold = conf.modThreshold
        self.seqThreshold = conf.seqThreshold

        self.unshifted = {}
        for k in range(8,255):
            sym = self.im.get_keyval(k,0)
            istext, string = keysym_desc(sym)
            if istext:
                self.unshifted[k] = string

        code_s = self.lookup_keysym
        self.modmap = { code_s(s) or s: mod for s, mod in conf.modmap.items()}
        for k,v in self.modmap.items():
            #this is a bit brittle, but works under circumstances.
            if v == LEVEL3:
                self.unshifted[k] = 'T'

        # NB: depends on modmap:
        self.keymap = { k:self.translate_keymap(v) for k,v in conf.keymap.items() }
        self.parents = conf.parents

        self.ignore = { code_s(s) for s in conf.ignore}
        self.ch_char  = conf.ch_char
        self.chordorder = conf.chordorder
        self.reset_callback = conf.on_reset

        if conf.logs:
            if self.real_logger is None:
                self.real_logger = Logger("keys")
            self.logger = self.real_logger
        else:
            self.logger = DummyLogger()
        self.logger("config", list(self.modmap.items()), self.serialize_xkeymap(), self.serialize_keymap())

    def serialize_xkeymap(self):
        arr = []
        modes = [0, SHIFT, LEVEL3, LEVEL3 | SHIFT]
        for code in range(8,255):
            ia = [self.im.get_keyval(code, s) for s in modes]
            arr.append(ia)
        return arr

    def serialize_keymap(self):
        maps = {}
        for name, keymap in self.keymap.items():
            maps[name] = list([k, self.serialize_action(v)] for (k,v) in keymap.items())
        return maps

    def on_reset(self):
        self.set_mode('')
        self.reset_callback()

    def set_quiet(self, val=None):
        if val is None:
            val = not self.quiet
        self.quiet = val

    def run(self):
        try:
            self.kb.run()
        except KeyboardInterrupt:
            pass

    def pause(self):
        pass

    def set_mode(self, mode, keymap=None):
        self.logger("set_mode", mode, keymap)

        self.mode = mode
        self.lock = None
        if keymap not in self.keymap:
            keymap = "base" if mode == 'n' else "insert"
        self.base_keymap = keymap
        self.update_keymap()

    def set_keymap(self, name):
        self.base_keymap = keymap
        self.update_keymap()

    def set_lock(self, name):
        self.lock = name
        self.update_keymap()

    def toggle_lock(self, name):
        if self.lock == name:
            self.lock = None
        else:
            self.lock = name
        self.update_keymap()

    def update_keymap(self):
        order = [self.base_keymap]
        if self.lock:
            order = [self.lock] + order
        n = 0
        while n < len(order):
            for p in self.parents.get(order[n],[]):
                if p not in order:
                    order.append(p)
            n += 1
        self.logger("set_keymap", order)
        self.remap.maps = [self.keymap[i] for i in order]

    def on_new_sequence(self, keyval, keycode, state, time):
        if keycode in self.ignore:
            return False
        self.logger('newseq')
        self.seq = []
        self.down = {}
        #FIXME: is a set; acts like a boolean
        self.alive = set()
        self.nonchord = set()
        self.seq_time = time
        self.last_nonchord = 0
        return True

    def on_press(self, keyval, keycode, state, time, pressed):
        self.logger('press', keycode, state, keyval, keysym_desc(keyval), time-self.seq_time)
        p = Press(keyval, keycode, state, time)
        self.down[keycode] = p
        self.alive.add(keycode)
        self.seq.append(p)
        if time < self.last_nonchord + self.seqThreshold:
            # prevent "thi" to become th[HI]
            self.nonchord.add(keycode)
        self.last_time = time
        self.im.schedule(0,self.update_display)
        return True

    def on_release(self, keyval, keycode,state,time,pressed):
        self.logger('release', keycode, state, keyval, keysym_desc(keyval), time-self.seq_time, bool(self.alive))
        self.im.schedule(0,self.update_display)
        if not self.alive:
            return
        l = {}
        is_chord, res = self.get_chord(time,keycode, log=l)
        self.logger("emit", is_chord, self.serialize_action(res), l["keycodes"], l["hold"], l["reason"])

        if not is_chord: # sequential mode
            self.last_nonchord = time
            self.nonchord.update(self.alive)
        self.alive.clear()
        self.nonchord.discard(keycode)
        self.seq = []
        del self.down[keycode]
        if res: self.im.show_preedit('')
        self.activate(res)
        self.last_time = time
        return True

    def on_repeat(self, *a):
        pass # (:

    def activate(self, seq):
        if callable(seq):
            seq()
        elif isinstance(seq, str):
            self.im.commit_string(seq)
        elif isinstance(seq, Press):
            self.im.fake_stroke(*seq[:3])
        elif isinstance(seq, Command):
            prefix  = '÷÷' if seq.hold else '××'
            self.im.commit_string(prefix+seq.cmd)
        else:
            for p in seq:
                self.activate(p)

    def display(self, seq, quiet=False, alone=True):
        if isinstance(seq, str):
            return seq
        elif isinstance(seq, list):
            return ''.join(self.display(p,quiet,len(seq) == 1) for p in seq)
        elif isinstance(seq, Press):
            sym, code, state = seq[:3]
            if sym is None:
                sym = self.im.get_keyval(code, state)
            istext, desc = keysym_desc(sym)
            if (quiet or alone) and not istext:
                return ''
            desc = desc_table.get(desc,desc)
            if state & CTRL:
                if quiet:
                    return ''
            return desc
        elif isinstance(seq, Command):
            if seq.hold:
                return '<'+seq.cmd.upper()+'>'
            else:
                return '['+seq.cmd+']'
        else:
            return 'X'

    def serialize_action(self, seq):
        if isinstance(seq, str):
            return [['str', seq]]
        elif isinstance(seq, list):
            return list(chain(self.serialize_action(a) for a in seq))
        elif isinstance(seq, Press):
            sym, code, state = seq[:3]
            if sym is None:
                sym = self.im.get_keyval(code, state)
            desc = keysym_desc(sym)
            return [['press', code, state, sym, desc]]
        elif isinstance(seq, Command):
            return [['cmd', seq.hold, seq.cmd]]
        else:
            return [['fun', repr(seq)]]

    def on_keymap_change(self):
        self.configure()

    def on_sock_poll(self):
        try: #FIXME: handle zmq errors?
            while self.sock.getsockopt(zmq.EVENTS) & zmq.POLLIN:
                msg = self.sock.recv_json()
                self.on_msg(msg)
        except Exception:
            traceback.print_exc()

        return True #continue watching

    def on_msg(self, msg):
        self.logger("msg", msg)
        cmd = msg[0]
        if cmd == "set_mode":
            mode = msg[1]
            keymap = msg[2] if len(msg) >= 3 else None
            self.set_mode(mode, keymap)

    def update_display(self):
        t = time.time()*1000
        if self.quiet and t - self.seq_time < 50:
            self.im.schedule(50+1,self.update_display)
            self.im.show_preedit('')
            return
        tvar = Timevar(t)
        is_chord, chord = self.get_chord(tvar,0)
        disp = self.display(chord,self.quiet)
        self.im.show_preedit(disp)
        if tvar.has_delta:
            self.im.schedule(tvar.mindelta+1,self.update_display)

    def nc_map(self, press):
        if press.state == 0 and (press.keycode,) in self.remap:
            return self.remap[(press.keycode,)]
        return press

    def get_chord(self,time,keycode, log={}):
        if not self.alive:
            return True, []
        #FIXME: this is a quick hack for the current iteration
        nonchord = False, [self.nc_map(i) for i in self.seq]
        print(nonchord)
        n = len(self.down)
        times = sorted( p.time for p in self.down.values())
        chord = tuple(sorted([ code for code in self.down.keys()]))
        basechord = chord
        thres = self.holdThreshold if n<2 else self.holdThreshold2
        hold = time - self.last_time >= thres
        if hold:
            chord = (HOLD,)+chord
        modders = set(basechord) &  self.modmap.keys()


        log['keycodes'] = list(basechord)
        log['hold'] = hold
        if keycode in self.nonchord:
            log['reason'] = "prev_nonchord"
            return nonchord
        if len(self.alive) == 2 and n == 2 and not hold:
            # risk of conflict with slightly overlapping sequence
            hold2 = time - times[-2] >= self.chordThreshold2
            if keycode == self.seq[0].keycode and not hold2: # ab|ba is always chord
                th = self.chordTreshold
                if self.seq[0].keycode in modders:
                    th = self.modThreshold
                t0, t1 = times[-2:]
                t2 = time
                if t2-t1 < th*(t1-t0):
                    log['reason'] = 'close_seq'
                    return nonchord

        print( self.alive, chord, self.remap.get(chord))
        try:
            log['reason'] = 'remap'
            return True, self.remap[chord]
        except KeyError:
            pass

        statemod = 0
        if modders and not (hold and self.mode):
            state = reduce(or_, (self.modmap[k] for k in modders),0)
            modseq = []
            for p in self.seq:
                if p.keycode not in modders:
                    modseq.append(Press(None,p.keycode,state,0))
            if modseq:
                log['reason'] = 'modders'
                return True, modseq

        if len(basechord) == 1 and hold and HOLD in self.modmap:
            keycode, = basechord
            log['reason'] = 'onehold'
            return True, [Press(None,keycode,self.modmap[HOLD],0)]

        if len(basechord) == 2 and self.mode:
            try:
                txt = [self.unshifted[c] for c in basechord]
            except KeyError:
                return nonchord
            txt = ''.join(sorted(txt,key=self.chordorder.find))

            log['reason'] = 'command'
            return True, Command(txt,hold)
        log['reason'] = 'not_found'
        return nonchord
