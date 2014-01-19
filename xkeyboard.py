
from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import record, xtest
from Xlib.protocol import rq, event

import time, sys

#enum
IDLE = 0
GRABBED = 1
PASS_THRU = 2

class keyboardGrabber(object):
    def __init__(self):
        self.display = Display()
        self.root = self.display.screen().root

        #TODO: use key classes/categories/whatever
        self.grab_mask = [XK.XK_Control_L, XK.XK_Control_R, XK.XK_Alt_L] 

    def run(self):
        grab_window = self.get_target()
        #grab_window.change_attributes(event_mask = X.KeyPressMask|X.KeyReleaseMask)
        grab_window.grab_key(X.AnyKey, X.AnyModifier, True,X.GrabModeSync, X.GrabModeSync)

        self.state = 0
        self.pressed = 0
        while 1:
            ev = self.display.next_event()
            self._handle_event(ev)
            self.display.allow_events(X.AsyncKeyboard, X.CurrentTime)

    def _handle_event(self,ev):
        print ev
        if self.state == IDLE:
            self._new_sequence(ev)

        if self.state == GRABBED:
            self._sequence_event(ev)
        else:
            self._passthru_event(ev)
        print self.state, self.pressed

    def _new_sequence(self,ev):
        assert ev.type == X.KeyPress
        #this logic shall move outside the X layer
        #if self.on_sequence_new(ev):
        key = self.display.keycode_to_keysym(ev.detail,0)
        print key, XK.XK_Alt_L
        if key in self.grab_mask or ev.state & 4:
            self.state = PASS_THRU
        else:
            self.state = GRABBED

    def _sequence_event(self,ev):
        if  ev.type == X.KeyPress:
            self.pressed += 1
            self.on_press(ev)
        elif ev.type == X.KeyRelease:
            ev2 = None
            if self.display.pending_events():
                ev2 = self.display.next_event()
                print ev2
                if ev2.type == X.KeyPress and ev2.time == ev.time and ev2.detail == ev.detail:
                    self.on_repeat(ev2)
                    return

            self.pressed -= 1
            if self.pressed == 0:
                self.state = IDLE
            # on_release might set state
            self.on_release(ev)
            if ev2 is not None:
                self._sequence_event(ev2)

    def _passthru_event(self,ev):
        window = self.get_target()
        window.send_event(ev)
        if  ev.type == X.KeyPress:
            self.pressed += 1
        elif ev.type == X.KeyRelease:
            ev2 = None
            if self.display.pending_events():
                ev2 = self.display.next_event()
                window.send_event(ev)
                # we need to handle this to not underflow self.pressed
                if ev2.type == X.KeyPress and ev2.time == ev.time and ev2.detail == ev.detail:
                    window.send_event(ev2)
                else:
                    self.pressed -= 1
                    self._passthru_event(ev2)
            else:
                self.pressed -= 1
        assert self.pressed >=0
        if self.pressed == 0:
            self.state = IDLE

    # on_... should be overidden
    def on_press(self,ev):
        print "PRESS", ev.detail, ev.state

    def on_release(self,ev):
        print "RELEASE", ev.detail, ev.state
        if ev.detail == 10:
            self.send_key('1')
        sym0 = self.display.keycode_to_keysym(ev.detail,0)
        if sym0 == XK.XK_Escape:
            sys.exit(0)

    def on_repeat(self,ev):
        #print "REPEAT", ev
        pass

    def get_target(self):
        return self.display.get_input_focus()._data["focus"]

    def fake_event(self,typeof,keycode,shift_state=0,window=None):
        if window is None:
            window = self.get_target()
        #whatif window == root, possible?
        shift_mask =0 
        ev = event.event_class[typeof](
            time = int(time.time()),
            root = self.root,
            window = window,
            same_screen = 0, child = X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = shift_state,
            detail = keycode
            )
        window.send_event(ev, propagate = True)

    #FIXME: we might want to send chars not mapped on keyboard
    def send_key(self,char):
        keysym = XK.string_to_keysym(char)
        keycode = self.display.keysym_to_keycode(keysym)
        self.fake_event(X.KeyPress, keycode)
        self.fake_event(X.KeyRelease, keycode)

if __name__ == "__main__":
    keyboardGrabber().run()
