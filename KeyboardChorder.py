from xkeyboard import KeyboardGrabber

IDLE = 0
READY = 0


class KeyboardChorder(object):
    def __init__(self):
        self.kb = KeyboardGrabber(self)

    def run(self):
        self.state = IDLE
        self.kb.run()
       
    def on_new_sequence(self, *a):
        self.seq = []
        self.dead = set()
        return True

    def on_press(self,keycode,state,time,pressed):
        keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        self.seq.append(keysym)
        print "PRESS", keycode, state, pressed
        self.last_time = time

    def on_release(self,keycode,state,time,pressed):
        keysym = self.kb.keycode_to_keysym(keycode,0) #[sic]
        if keysym in self.dead:
            self.dead.remove(keysym)
        else:
            if self.is_chord(time): # 
                self.emit_chord()
                self.dead.update([k for k in self.seq if k != keysym])
            else:
                self.emit_key(keycode,state)
        self.seq.remove(keysym)

    def on_repeat(self, *a):
        pass # (:

    def is_chord(self,time):
        #this is ALL WRONG
        return time - self.last_time >= 500


    def emit_key(self,keycode,state):
        print "EMIT", keycode, state

    def emit_chord(self):
        chord = sorted(self.seq)
        print chord

if __name__ == "__main__":
    KeyboardChorder().run()
