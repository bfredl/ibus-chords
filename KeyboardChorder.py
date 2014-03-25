# -*- coding: utf-8 -*-
from xkeyboard import KeyboardGrabber
from Xlib import XK
from operator import or_

SHIFT = 0x01
LEVEL3 = 0x80

class KeyboardChorder(object):
    def __init__(self):
        self.kb = KeyboardGrabber(self)
        self.modThreshold = 200
        self.chordTreshold = 2.0

        self.configure()

    def configure(self):
        chords = {
            'eh': 'F',
            'ut': 'f'
        }

        modmap = {
            'HOLD': SHIFT,
            'space': LEVEL3,
            'Escape': LEVEL3 | SHIFT,
        }
        ignore = { 'BackSpace', 'Control_L', 'Shift_L', 0xFE03, 'Alt_L'}
        ch_code = u'ö'

        def pair(ch):
            return self.kb.lookup_char(ch)[0]
        def code_s(s):
            if s == 'HOLD': return s
            syms = self.kb.lookup_keysym(s)
            return syms[0][0] if syms else s

        self.remap = {}
        for desc, val in chords.items():
            chord = []
            for ch in desc:
                chord.append(pair(ch)[0])
            if isinstance(val, basestring):
                seq = [ self.kb.lookup_char(ch)[0] for ch in val]
            else:
                seq = val
            self.remap[tuple(chord)] = seq 

        self.modmap = { code_s(s) or s: mod for s, mod in modmap.iteritems()}
        print self.modmap
        self.ignore = { self.kb.lookup_keysym(s)[0] for s in ignore}
        self.ch_code  = pair(ch_code)

    def run(self):
        try:
            self.kb.run()
        except KeyboardInterrupt:
            pass
            
    def on_new_sequence(self, keycode, state):
        if keycode in self.ignore:
            return False 
        self.seq = []
        self.times = []
        self.dead = set()
        return True

    def on_press(self,keycode,state,time,pressed):
        self.seq.append(keycode)
        self.times.append(time)
        self.last_time = time

    def on_release(self,keycode,state,time,pressed):
        if keycode in self.dead:
            self.dead.remove(keycode)
        else:
            if self.is_chord(time,keycode): 
                dead = self.emit_chord(keycode)
                if dead:
                    self.dead.update([k for k in dead if k != keycode])
                else:
                    self.emit_key(keycode,state)
            else:
                self.emit_key(keycode,state)
        self.seq.remove(keycode)
        self.last_time = time

    def on_repeat(self, *a):
        pass # (:

    def is_chord(self,time,keycode=None):
        n = len(self.seq)
        if len(self.dead) > 0:
            return True # not _completely_ correct, but
        if n == 1:
            return time - self.last_time >= self.modThreshold
        if n == 2:
            if keycode == self.seq[1]: # ab|ba is always chord
                return True
            t0, t1 = self.times[-2:]
            t2 = time
            return t2-t1 > (self.chordTreshold)*(t1-t0) 
        if n >= 3:
            return True

    def emit_key(self,keycode,state):
        self.kb.fake_stroke(keycode,state)
        #print "EMIT", keycode, state

    #FIXME: merge w in_chord
    def emit_chord(self,keycode):
        chord = tuple(sorted(self.seq))
        #keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if chord in self.remap:
            seq = self.remap[chord]
            for key in seq:
                self.kb.fake_stroke(*key)
            return chord

        modmap = self.modmap
        modders = set(chord) &  modmap.viewkeys()
        if modders and len(chord) >= len(modders) + 1:
            state = reduce(or_, (modmap[k] for k in modders))
            if keycode in (set(chord) - modders):
                self.kb.fake_stroke(keycode,state)
                return modders
            else:
                return False


        if len(chord) == 1:
            keycode, = chord
            self.kb.fake_stroke(keycode,modmap['HOLD'])
            return chord
        else:
            return False
            self.kb.fake_stroke(*self.ch_code)
            for key in chord:
                self.kb.fake_stroke(*key)
            print ""

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
