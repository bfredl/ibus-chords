from xkeyboard import KeyboardGrabber

IDLE = 0
READY = 0


class KeyboardChorder(object):
    def __init__(self):
        self.kb = KeyboardGrabber(self)
        self.ds = []
        self.modThreshold = 300
        self.chordTreshold = 300

    def run(self):
        self.state = IDLE
        try:
            self.kb.run()
        except KeyboardInterrupt:
            print repr(self.ds)
            
       
    def on_new_sequence(self, *a):
        self.seq = []
        self.times = []
        self.dead = set()
        return True

    def on_press(self,keycode,state,time,pressed):
        keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        self.seq.append(keysym)
        self.times.append(time)
        self.last_time = time

    def on_release(self,keycode,state,time,pressed):
        keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if keysym in self.dead:
            self.dead.remove(keysym)
        else:
            if self.is_chord(time,keysym): # 
                self.emit_chord()
                self.dead.update([k for k in self.seq if k != keysym])
            else:
                self.emit_key(keycode,state)
        self.seq.remove(keysym)

    def on_repeat(self, *a):
        pass # (:

    def is_chord(self,time,keysym=None):
        n = len(self.seq)
        if len(self.dead) > 0:
            return True # not _completely_ correct, but
        if n == 1:
            return time - self.last_time >= 300
        if n == 2:
            if keysym == self.seq[1]:
                return True
            t0, t1 = self.times[-2:]
            t2 = time
            #print t2-t1, t1-t0
            self.ds.append((t2-t0,t1-t0))
            return False#t2-t1 > 2*(t1-t0) #test

    def emit_key(self,keycode,state):
        self.kb.fake_event(2,keycode,state)
        self.kb.fake_event(3,keycode,state)
        #print "EMIT", keycode, state

    def emit_chord(self):
        chord = sorted(self.seq)
        print chord

if __name__ == "__main__":
    KeyboardChorder().run()
