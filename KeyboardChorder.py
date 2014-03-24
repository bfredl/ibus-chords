from xkeyboard import KeyboardGrabber
from Xlib import XK
from operator import or_

IDLE = 0
READY = 0

SHIFT = 0x01
GROUP3 = 0x80

class KeyboardChorder(object):
    def __init__(self):
        self.kb = KeyboardGrabber(self)
        self.modThreshold = 200
        self.chordTreshold = 2.0

        self.remap = {
            (41,45): (29,0),
            (40,44): (29,1)
        }
        self.modmap = {
            'HOLD': SHIFT,
            65: GROUP3,
            66: GROUP3 | SHIFT,
        }
        self.ignore = { 50, 94, 22 }
        self.ch_code = (53,0x80)

    def run(self):
        self.state = IDLE
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
            if self.is_chord(time,keycode) and self.emit_chord():
                self.dead.update([k for k in self.seq if k != keycode])
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

    def emit_key(self,keycode,state):
        self.kb.fake_stroke(keycode,state)
        #print "EMIT", keycode, state

    def emit_chord(self):
        chord = tuple(sorted(self.seq))
        #keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if chord in self.remap:
            val = self.remap[chord]
            self.kb.fake_stroke(*val)
            return True

        modmap = self.modmap
        modders = set(chord) &  modmap.viewkeys()
        if modders and len(chord) == len(modders) + 1:
            state = reduce(or_, (modmap[k] for k in modders))
            keycode = (set(chord) - modders).pop()
            self.kb.fake_stroke(keycode,state)
            return True


        if len(chord) == 1:
            keycode, = chord
            self.kb.fake_stroke(keycode,modmap['HOLD'])
            return True
        else:
            return False
            self.kb.fake_stroke(*self.ch_code)
            for key in chord:
                self.kb.fake_stroke(key,0)
            print ""

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
