# -*- coding: utf-8 -*-
from xkeyboard import KeyboardGrabber, keysym_to_str, islatin
from Xlib import XK
from operator import or_
from collections import namedtuple
import os.path as path
import time

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
Ins = namedtuple('Ins', ['txt'])
MAGIC = 512
class KeyboardChorder(object):
    def __init__(self, im):
        self.im = im
        self.conf_file = path.expanduser('~/.config/chords')
        self.configure()
        self.on_reset()

    def configure(self):
        #FIXME: place these in a class w defaults
        def Sym(s):
            keysym = XK.string_to_keysym(s)
            keycode, keyval = self.im.lookup_keysym(keysym)[0]
            return Press(keysym, keycode, keyval, 0)

        conf = SimpleNamespace(
            pause=self.pause,
            conf=self.configure,
            switch=self.toggle_mode,
            Shift=Shift,
            Sym=Sym,
            Ins=Ins,
            SHIFT=0x01,
            CTRL=0x04,
            LEVEL3=0x80,
        )
        execfile(self.conf_file,conf.__dict__)
        self.holdThreshold = conf.holdThreshold
        self.holdThreshold2 = conf.holdThreshold2
        self.chordTreshold = conf.chordTreshold
        self.modThreshold = conf.modThreshold
        self.dispEagerness = 50

        def code_s(s):
            if s == 'HOLD': return s
            syms = self.im.lookup_keysym(s)
            return syms[0][0] if syms else s
        self.unshifted = {}
        for k in range(8,255):
            sym = self.im.get_keyval(k,0)
            if islatin(sym): #FIXME: discrimination against non-latin-1 script :(
                self.unshifted[k] = chr(sym)

        self.remap = {}
        # FIXME: split Shift pairs and modes HERE
        for desc, val in conf.chords.items():
            if isinstance(desc, basestring):
                chord = []
                for ch in desc:
                    chord.append(code_s(ch))
            elif isinstance(desc, Press):
                print desc
                chord = (desc.keycode,)

            self.remap[tuple(sorted(chord))] = val 
        print self.remap

        self.modmap = { code_s(s) or s: mod for s, mod in conf.modmap.iteritems()}
        self.ignore = { code_s(s) for s in conf.ignore}
        self.ignore.add(108)
        self.ch_char  = conf.ch_char
        self.chordorder = conf.chordorder

    def on_reset(self):
        self.command_mode = False

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
        self.command_mode = not self.command_mode

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
            print '+', self.psym(keyval), time-self.seq_time
        return not self.seq_d

    def on_release(self, keyval, keycode,state,time,pressed):
        if keycode >= MAGIC:
            return True
        if dbg:
            print '-', self.psym(keyval), time-self.seq_time
        if keycode in self.dead:
            self.dead.remove(keycode)
            res = []
            dead = ()
        else:
            hold = time - self.last_time >= self.holdThreshold
            dead, res = self.get_chord(time,keycode,hold)
            if not dead:
                #TODO: maybe latch 'sequential mode'?
                dead = self.down.keys()
                res = list(self.seq)
                self.seq_d = True
        self.dead.update([k for k in dead if k != keycode])
        self.seq = [p for p in self.seq if p.keycode not in dead]
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
        elif isinstance(seq, basestring):
            self.im.commit_string(seq)
        elif isinstance(seq, Press):
            self.im.fake_stroke(*seq[:3])
        else:
            for p in seq:
                self.activate(p)

    def display(self, seq):
        if isinstance(seq, basestring):
            return seq
        elif isinstance(seq, list):
            return ''.join(self.display(p) for p in seq)
        elif isinstance(seq, Press):
            sym, code, state = seq[:3]
            if sym is None:
                sym = self.im.get_keyval(code, state)
            desc = keysym_to_str(sym)
            if state & CTRL:
                desc = 'C-'+desc
            return desc
        else:
            return 'X'

    def on_keymap_change(self):
        self.configure()

    def on_magic(self, code, keyval):
        if code == 0:
            if keyval == ord('n'):
                self.command_mode = True
            elif keyval == ord('i'):
                self.command_mode = False

    def update_display(self):
        t = time.time()*1000 + self.dispEagerness
        if set(self.down) - self.dead:
            wait = (self.last_time + self.holdThreshold) - t
            d, chord = self.get_chord(self.last_time,0,wait<=0)
            if not d: chord = self.seq
            print self.seq, repr(chord)
            disp = self.display(chord)
            self.im.show_preedit(disp)
            if wait > 0:
                self.im.schedule(wait+1,self.update_display)
        else:
            self.im.show_preedit('')

    def get_chord(self,time,keycode,hold):
        nochord = ((), [])
        n = len(self.down)
        times = sorted( p.time for p in self.down.values())
        chord = tuple(sorted([ p.keycode for p in self.down.values()]))
        modders = set(chord) &  self.modmap.viewkeys()
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
                        return nochord

        #keysym = self.im.keycode_to_keysym(keycode,0) #[sic]
        seq = self.remap.get(chord,None)
        if isinstance(seq, Shift):
            seq = seq.hold if hold else seq.base
        if isinstance(seq, Ins):
            if self.command_mode:
                seq = None
            else:
                seq = seq.txt
        if seq is not None: return chord, seq

        state = reduce(or_, (self.modmap[k] for k in modders),0)
        if modders:
            modseq = []
            for p in self.seq:
                if p.keycode not in modders:
                    modseq.append(Press(None,p.keycode,state,0))
            if modseq:
                return chord, modseq

        if len(chord) == 1 and hold:
            keycode, = chord
            return chord, [Press(None,keycode,self.modmap['HOLD'],0)]
        if len(chord) == 2 and self.command_mode:
            prefix  = '÷÷' if hold else '××'
            try:
                desc = [self.unshifted[c] for c in chord]
            except KeyError:
                return nochord
            desc = ''.join(sorted(desc,key=self.chordorder.find))

            #FIXME; RETHINK
            return chord, prefix+desc
        return nochord

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
