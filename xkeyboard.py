
from Xlib import X, XK
from Xlib.display import Display
from Xlib.ext import record, xtest
from Xlib.protocol import rq, event

import time, sys

class keyboardGrabber(object):
    def __init__(self):
        self.display = Display()
        self.root = self.display.screen().root


    def run(self):
        #thanksto: @tino at stackoverflow
        self.root.change_attributes(event_mask = X.KeyPressMask|X.KeyReleaseMask)
        self.root.grab_key(10, 0, True,X.GrabModeSync, X.GrabModeSync)

        while 1:
            ev = self.display.next_event()
            print "event"
            self.handle_event(ev)
            self.display.allow_events(X.AsyncKeyboard, X.CurrentTime)

    def handle_event(self,ev):
        if  ev.type == X.KeyPress:
            self.on_press(ev)
        elif ev.type == X.KeyRelease:
            ev2 = None
            if self.display.pending_events():
                ev2 = self.display.next_event()
                if ev2.type == X.KeyPress and ev2.time == ev.time and ev2.detail == ev.detail:
                    self.on_repeat(ev2)
                    return

            self.on_release(ev)
            if ev2 is not None:
                self.handle_event(ev2)
        else:
            print "?????", ev

    def on_press(self,ev):
        print "PRESS", ev

    def on_release(self,ev):
        print "RELEASE", ev
        if ev.detail == 10:
            self.send_key('1')
        sym0 = self.display.keycode_to_keysym(ev.detail,0)
        if sym0 == XK.XK_Escape:
            sys.exit(0)

    def on_repeat(self,ev):
        print "REPEAT", ev

    #UNTESTED
    def fake_event(self,typeof,keycode,window=None):
        if window is None:
            window = self.display.get_input_focus()._data["focus"]
        shift_mask =0 #place ctrl/etc in here?
        ev = event.event_class[typeof](
            time = int(time.time()),
            root = self.root,
            window = window,
            same_screen = 0, child = X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = shift_mask,
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
