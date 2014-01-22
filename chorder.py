from xkeyboard import KeyboardGrabber
#from .txtdisplay import Display

IDLE = 0
ACTIVE = 1
ABORTED = 2

class KeyboardChorder(KeyboardGrabber):
    def __init__(self):
        KeyboardGrabber.__init__(self)
        #self.display = Display()
        self.seqstate = IDLE

    def on_sequence_new(self,keycode,state,time):
        self.seq = []
        self.starttime = time
        self.seqstate = ACTIVE

    def on_press(self,keycode,state,time):
        self.seq.append((keycode,state))
        if self.pressed == 2:
            self.seqstate = ABORTED

    def on_release(self,keycode,state,time):
        if self.pressed == 0:
            if self.seqstate == ACTIVE:
                print keycode, time-self.starttime
            self.seqstate = IDLE

if __name__ == "__main__":
    KeyboardChorder().run()
