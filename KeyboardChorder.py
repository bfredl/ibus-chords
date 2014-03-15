from xkeyboard import KeyboardGrabber
from Xlib import XK

IDLE = 0
READY = 0


class KeyboardChorder(object):
    def __init__(self):
        self.kb = KeyboardGrabber(self)
        self.modThreshold = 300
        self.chordTreshold = 2.0

    def run(self):
        self.state = IDLE
        try:
            self.kb.run()
        except KeyboardInterrupt:
            pass
            
       
    def on_new_sequence(self, keycode, state):
        keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if keysym == XK.XK_Shift_L:
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
            if self.is_chord(time,keycode): # 
                self.emit_chord()
                self.dead.update([k for k in self.seq if k != keycode])
            else:
                self.emit_key(keycode,state)
        self.seq.remove(keycode)

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
        chord = sorted(self.seq)
        #keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if len(chord) == 1:
            keycode, = chord
            self.kb.fake_stroke(keycode,4)
        else:
            self.kb.fake_stroke(self.ch_code,self.ch_state)
            for key in chord:
                self.kb.fake_stroke(key,0)
            print chord

if __name__ == "__main__":
    KeyboardChorder().run()
