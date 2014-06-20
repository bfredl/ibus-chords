# -*- coding: utf-8 -*-
from __future__ import print_function
from operator import or_
from collections import namedtuple, ChainMap
import os.path as path
import time
from keysym import desc_to_keysym, keysym_desc
import sys
from functools import reduce
from types import SimpleNamespace


desc_table = {
        'Return': '↩',
        'BackSpace': '◄',
        # FIXME: these from the modmap
        'Control_L': 'C-',
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

dbg = True
def runfile(fname, glob):
    with open(fname, 'rb') as f:
        exec(compile(f.read(), fname, 'exec'), glob, glob)

Press = namedtuple('Press', ['keyval','keycode','state','time'])
Shift = namedtuple('Shift', ['base', 'hold'])
Command = namedtuple('Command', ['cmd', 'hold'])
MAGIC = 512
class KeyboardChorder(object):
    def __init__(self, im):
        self.im = im
        self.conf_file = path.expanduser('~/.config/chords')
        self.remap = ChainMap()
        self.configure()
        self.on_reset()
        self.quiet = False

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
                    chord.append(self.lookup_keysym(ch))
                chord = tuple(sorted(chord))
            elif isinstance(desc, Press):
                chord = (desc.keycode,)

            if isinstance(val, Shift):
                if val.base is not None:
                    km[chord] = val.base
                km[(HOLD,)+chord] = val.hold
            else:
                km[chord] = val
        return km

    def configure(self):
        #FIXME: place these in a class w defaults
        def Sym(s):
            keysym = desc_to_keysym(s)
            keycode, keyval = self.im.lookup_keysym(keysym)[0]
            return Press(keysym, keycode, keyval, 0)

        conf = SimpleNamespace(
            pause=self.pause,
            quiet=self.set_quiet,
            conf=self.configure,
            switch=self.toggle_mode,
            keymap={},
            parents={},
            Shift=Shift,
            Sym=Sym,
            SHIFT=0x01,
            CTRL=0x04,
            ALT=ALT,
            LEVEL3=0x80,
        )
        runfile(self.conf_file,conf.__dict__)
        self.holdThreshold = conf.holdThreshold
        self.holdThreshold2 = conf.holdThreshold2
        self.chordTreshold = conf.chordTreshold
        self.modThreshold = conf.modThreshold
        self.dispEagerness = 50

        self.unshifted = {}
        for k in range(8,255):
            sym = self.im.get_keyval(k,0)
            istext, string = keysym_desc(sym)
            if istext:
                self.unshifted[k] = string

        self.keymap = { k:self.translate_keymap(v) for k,v in conf.keymap.items() }
        self.parents = conf.parents
        print(self.keymap)
        print(self.unshifted)

        code_s = self.lookup_keysym
        self.modmap = { code_s(s) or s: mod for s, mod in conf.modmap.items()}
        self.ignore = { code_s(s) for s in conf.ignore}
        self.ch_char  = conf.ch_char
        self.chordorder = conf.chordorder

    def on_reset(self):
        self.set_mode('')

    def set_quiet(self, val=None):
        if val is None:
            val = not self.quiet
        self.quiet = val

    def psym(self,val):
        if 0x20 <= val < 0x80 or 0xa0 <= val < 0x0100:
            return chr(val)
        else:
            return val

    def run(self):
        try:
            self.kb.run()
        except KeyboardInterrupt:
            pass

    def pause(self):
        pass

    def toggle_mode(self):
        # HACK: generalize to n diffrent modes
        self.set_mode('' if self.mode else 'n')
        self.update_mode()

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'n':
            self.set_keymap("base")
        else:
            self.set_keymap("insert")

    def set_keymap(self, name):
        order = [name]
        n = 0
        while n < len(order):
            for p in self.parents.get(order[n],[]):
                if p not in order:
                    order.append(p)
            n += 1
        self.remap.maps = [self.keymap[i] for i in order]

    def on_new_sequence(self, keyval, keycode, state, time):
        if keycode in self.ignore:
            return False 
        self.seq = []
        self.down = {}
        self.dead = set()
        self.seq_time = time 
        self.seq_d = False
        self.last_nonchord = 0
        return True

    def on_press(self, keyval, keycode, state, time, pressed):
        if keycode >= MAGIC:
            self.on_magic(keyval,keycode-MAGIC)
            return True
        p = Press(keyval, keycode, state, time)
        self.down[keycode] = p
        if not self.seq_d:
            self.seq.append(p)
        else:
            self.dead.add(keycode)
        self.last_time = time
        self.im.schedule(0,self.update_display)
        if dbg:
            print('+', self.psym(keyval), time-self.seq_time)
        return not self.seq_d

    def on_release(self, keyval, keycode,state,time,pressed):
        if keycode >= MAGIC:
            return True
        if dbg:
            print('-', self.psym(keyval), time-self.seq_time)
        print(self.down.keys(), self.dead)
        if self.down.keys() - self.dead:
            hold = time - self.last_time >= self.holdThreshold
            res = self.get_chord(time,keycode,hold)
            if not res:
                res = list(self.seq)
                self.seq_d = True
        else:
            res = []
        self.dead.update([k for k in self.down if k != keycode])
        self.seq = []
        del self.down[keycode]
        if res: self.im.show_preedit('')
        self.activate(res)
        self.last_time = time
        self.im.schedule(0,self.update_display)
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

    def display(self, seq,quiet=False):
        if isinstance(seq, str):
            return seq
        elif isinstance(seq, list):
            return ''.join(self.display(p,quiet) for p in seq)
        elif isinstance(seq, Press):
            sym, code, state = seq[:3]
            if sym is None:
                sym = self.im.get_keyval(code, state)
            istext, desc = keysym_desc(sym)
            if quiet and not istext:
                return ''
            desc = desc_table.get(desc,desc)
            if state & CTRL:
                if not quiet:
                    desc = 'C-'+desc
                else:
                    return ''
            return desc
        elif isinstance(seq, Command):
            if seq.hold:
                return '<'+seq.cmd.upper()+'>'
            else:
                return '['+seq.cmd+']'
        else:
            return 'X'

    def on_keymap_change(self):
        self.configure()

    def on_magic(self, keyval, code):
        print('magic', keyval, code)
        if code == 0:
            if keyval in range(ord('a'), ord('z')):
                self.set_mode(chr(keyval))
            if keyval in range(ord('A'), ord('Z')):
                self.set_mode(chr(keyval).lower())

    def update_display(self):
        t = time.time()*1000
        tlast = t- self.last_time 
        if self.quiet and t - self.seq_time < 50:
            self.im.schedule(50+1,self.update_display)
            self.im.show_preedit('')
            return
        if set(self.down) - self.dead:
            wait = (self.holdThreshold - self.dispEagerness) - tlast
            chord = self.get_chord(self.last_time,0,wait<=0)
            if chord is None: chord = self.seq
            print(self.seq, repr(chord))
            disp = self.display(chord,self.quiet)
            self.im.show_preedit(disp)
            if wait > 0:
                self.im.schedule(wait+1,self.update_display)
        else:
            self.im.show_preedit('')

    def get_chord(self,time,keycode,hold):
        n = len(self.down)
        times = sorted( p.time for p in self.down.values())
        chord = tuple(sorted([ code for code in self.down.keys()]))
        basechord = chord
        if hold:
            chord = (HOLD,)+chord
        modders = set(basechord) &  self.modmap.keys()
        if len(self.dead) == 0:
            # risk of conflict with slightly overlapping sequence
            if n == 2 and not hold:
                hold2 = time - times[-2] >= self.holdThreshold2
                if keycode == self.seq[0].keycode and not hold2: # ab|ba is always chord
                    th = self.chordTreshold
                    if self.seq[0].keycode in modders:
                        th = self.modThreshold
                    t0, t1 = times[-2:]
                    t2 = time
                    if t2-t1 < th*(t1-t0):
                        return None

        try:
            return self.remap[chord]
        except KeyError:
            pass

        statemod = 0
        if modders:
            state = reduce(or_, (self.modmap[k] for k in modders),0)
            modseq = []
            for p in self.seq:
                if p.keycode not in modders:
                    modseq.append(Press(None,p.keycode,state,0))
            if modseq:
                return modseq

        if len(basechord) == 1 and hold:
            keycode, = basechord
            return [Press(None,keycode,self.modmap[HOLD],0)]

        if len(basechord) == 2 and self.mode != '':
            try:
                txt = [self.unshifted[c] for c in basechord]
            except KeyError:
                return None
            txt = ''.join(sorted(txt,key=self.chordorder.find))

            return Command(txt,hold)
        return None

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
