# -*- coding: utf-8 -*-
from xkeyboard import KeyboardGrabber
from Xlib import XK
from operator import or_
from collections import namedtuple
import os.path as path

SHIFT = 0x01
CTRL = 0x04
LEVEL3 = 0x80

dbg = True
class SimpleNamespace:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
    def __repr__(self):
        keys = sorted(self.__dict__)
        items = ("{}={!r}".format(k, self.__dict__[k]) for k in keys)
        return "{}({})".format(type(self).__name__, ", ".join(items))
    def __eq__(self, other):
        return self.__dict__ == other.__dict__

Press = namedtuple('Press', ['keyval','keycode','state','time'])
Shift = namedtuple('Shift', ['base', 'hold'])
class KeyboardChorder(object):
    def __init__(self, im):
        self.im = im
        self.conf_file = path.expanduser('~/.config/chords')
        self.configure()

    def configure(self):
        #FIXME: place these in a class w defaults
        def Sym(s):
            return [(None,)+self.im.lookup_keysym(s)[0]]
        conf = SimpleNamespace(
            pause=self.pause,
            conf=self.configure,
            Shift=Shift,
            Sym=Sym,
            SHIFT=0x01,
            CTRL=0x04,
            LEVEL3=0x80,
        )
        execfile(self.conf_file,conf.__dict__)
        self.holdThreshold = conf.holdThreshold
        self.holdThreshold2 = conf.holdThreshold2
        self.chordTreshold = conf.chordTreshold
        self.modThreshold = conf.modThreshold

        def code_s(s):
            if s == 'HOLD': return s
            syms = self.im.lookup_keysym(s)
            return syms[0][0] if syms else s

        self.remap = {}
        for desc, val in conf.chords.items():
            chord = []
            for ch in desc:
                chord.append(code_s(ch))
            self.remap[tuple(sorted(chord))] = val 
        print self.remap

        self.modmap = { code_s(s) or s: mod for s, mod in conf.modmap.iteritems()}
        self.ignore = { code_s(s) for s in conf.ignore}
        self.ignore.add(108)
        self.ch_char  = conf.ch_char

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

    def on_new_sequence(self, keyval, keycode, state, time):
        if keycode in self.ignore or (state & 4):
            return False 
        self.seq = []
        self.down = {}
        self.dead = set()
        self.seq_time = time 
        self.seq_d = False
        self.last_nonchord = 0
        return True

    def on_press(self, keyval, keycode, state, time, pressed):
        p = Press(keyval, keycode, state, time)
        self.down[keycode] = p
        if not self.seq_d:
            self.seq.append(p)
        else:
            self.dead.add(keycode)
        self.last_time = time
        self.update_display()
        if dbg:
            print '+', self.psym(keyval), time-self.seq_time
        return not self.seq_d

    def on_release(self, keyval, keycode,state,time,pressed):
        if dbg:
            print '-', self.psym(keyval), time-self.seq_time
        if keycode in self.dead:
            self.dead.remove(keycode)
            res = []
            dead = ()
        else:
            dead, res = self.get_chord(time,keycode)
            if not dead:
                #TODO: maybe latch 'sequential mode'?
                dead = self.down.keys()
                res = list(self.seq)
                self.seq_d = True
        self.dead.update([k for k in dead if k != keycode])
        self.seq = [p for p in self.seq if p.keycode not in dead]
        del self.down[keycode]
        if res: self.im.show_preedit('')
        if callable(res):
            res()
        elif isinstance(res, basestring):
            self.im.commit_string(res)
        else:
            for p in res:
                self.im.fake_stroke(*p[:3])
        self.last_time = time
        self.update_display()
        return True

    def on_repeat(self, *a):
        pass # (:

    def on_keymap_change(self):
        self.configure()

    def update_display(self):
        if self.down:
            self.im.show_preedit('{} {}'.format(len(self.down),len(self.seq)))
        else:
            self.im.show_preedit('')

    #FIXME: return actions instead for OSD preview
    def get_chord(self,time,keycode):
        nochord = ((), [])
        n = len(self.down)
        times = sorted( p.time for p in self.down.values())
        chord = tuple(sorted([ p.keycode for p in self.down.values()]))
        modders = set(chord) &  self.modmap.viewkeys()
        hold = time - self.last_time >= self.holdThreshold
        if len(self.dead) == 0:
            if n == 1 and not hold:
                return nochord
                    
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
                        return nochord

        #keysym = self.im.keycode_to_keysym(keycode,0) #[sic]
        if chord in self.remap:
            seq = self.remap[chord]
            if isinstance(seq, Shift):
                seq = seq.hold if hold else seq.base
            return chord, seq

        state = reduce(or_, (self.modmap[k] for k in modders),0)
        if modders:
            modseq = []
            for p in self.seq:
                if p.keycode not in modders:
                    modseq.append((None,p.keycode,state))
            if modseq:
                return chord, modseq

        if len(chord) == 1:
            keycode, = chord
            return chord, [(None,keycode,self.modmap['HOLD'])]
        else:
            #FIXME; RETHINK
            print('FAULT')
            return nochord

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
