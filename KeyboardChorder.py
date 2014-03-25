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
            'ut': 'f',
            'as': ' = ',
            'is': ' == ',
            '\'c': '\': \'',
            'oe': ' += ',
            'ht': '()'
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
            self.remap[tuple(sorted(chord))] = seq 

        self.modmap = { code_s(s) or s: mod for s, mod in modmap.iteritems()}
        self.ignore = { code_s(s) for s in ignore}
        self.ignore.add(108)
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
            dead = self.emit_chord(time,keycode)
            if dead:
                self.dead.update([k for k in dead if k != keycode])
            else: 
                self.emit_key(keycode,state)
        self.seq.remove(keycode)
        self.last_time = time

    def on_repeat(self, *a):
        pass # (:

    def on_keymap_change(self):
        self.configure()

    def emit_key(self,keycode,state):
        self.kb.fake_stroke(keycode,state)
        #print "EMIT", keycode, state

    #FIXME: return actions instead for OSD preview
    def emit_chord(self,time,keycode):
        n = len(self.seq)
        hold = time - self.last_time >= self.modThreshold
        if len(self.dead) == 0:
            if n == 1 and not hold:
                return False
                    
            # risk of conflict with slightly overlapping sequence
            if n == 2 and keycode == self.seq[0]: # ab|ba is always chord
                t0, t1 = self.times[-2:]
                t2 = time
                if t2-t1 < (self.chordTreshold)*(t1-t0):
                    return False

        chord = tuple(sorted(self.seq))
        #keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if chord in self.remap:
            seq = self.remap[chord]
            for key in seq:
                self.kb.fake_stroke(*key)
            return chord

        modmap = self.modmap
        modders = set(chord) &  modmap.viewkeys()
        state = reduce(or_, (modmap[k] for k in modders),0)
        other = set(chord) - modders
        if modders and other:
            if len(other) == 1:
                keycode = other.pop() 
            elif keycode not in other:
                return chord# ambigous: do nothing

            self.kb.fake_stroke(keycode,state)
            return modders | {keycode}


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
