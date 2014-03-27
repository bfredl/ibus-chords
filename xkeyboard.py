from Xlib import X,XK
import xcb, xcb.xproto as xproto 
from xcb.xproto import KeyPressEvent, KeyReleaseEvent
#import xcb.xinput

import struct
import time, sys

#enum
IDLE = 0
GRABBED = 1
PASS_THRU = 2

typemap = { KeyPressEvent:2, KeyReleaseEvent:3}
def InternAtom(core,string, only_if_exists=False):
    return core.InternAtom(only_if_exists, len(string), string).reply().atom

# Still leaks X abstraction (like any of your favourite X11 toolkit)
# bcuz one does not simply "abstract away" x keyboard semantics
# But wayland is xkb based anyways...
class KeyboardGrabber(object):
    def __init__(self,reciever):
        self.conn = xcb.connect()
        self.X = self.conn.core
        #self.XI = self.conn(xcb.xinput.key)
        self.root = self.conn.get_setup().roots[0].root

        self.grabExclude = [XK.XK_Super_L]

        #self.grab_mask = [XK.XK_Control_L, XK.XK_Control_R, XK.XK_Alt_L] 
        self._update_keymap()

        self.reciever = reciever 

        self.X.ChangeWindowAttributesChecked(self.root,X.CWEventMask,[X.PropertyChangeMask]).check()
        self._NET_ACTIVE_WINDOW = InternAtom(self.X, "_NET_ACTIVE_WINDOW")
        self.WINDOW = InternAtom(self.X, "WINDOW")

    def _grabkey(self):
        self.grab_window = self.target
        self.X.GrabKeyChecked(True, self.grab_window,0,0,xproto.GrabMode.Sync, xproto.GrabMode.Sync).check()

    def _ungrabkey(self):
        if self.grab_window is not None:
            try:
                self.X.UngrabKeyChecked(0,self.grab_window,0).check()
            except xproto.BadWindow:
                pass
            self.grab_window = None

    def run(self):
        self.grab_window = None
        self._handle_focus()

        self.state = 0
        self.pressed = 0
        self.kbdgrab = False
        self.should_pause = False

        try:
            while 1:
                ev = self.conn.wait_for_event()
                self._handle_event(ev)
        finally:
            if self.kbdgrab:
                self.X.UngrabKeyboardChecked(X.CurrentTime).check()
                self.kbdgrab = False
            self._ungrabkey()
            #self.X.AllowEventsChecked(X.AsyncKeyboard, X.CurrentTime).check()

    def _handle_event(self,ev):
        if isinstance(ev,xproto.PropertyNotifyEvent):
            if ev.atom == self._NET_ACTIVE_WINDOW:
                self._handle_focus()
            return

        elif isinstance(ev,(KeyPressEvent, KeyReleaseEvent)):
            assert self.grab_window != None
            if self.state == IDLE:
                self._new_sequence(ev)

            self._sequence_event(ev)
            self.X.AllowEventsChecked(X.AsyncKeyboard, X.CurrentTime).check()
        elif isinstance(ev,xproto.MappingNotifyEvent):
            self._update_keymap()
            self.reciever.on_keymap_change()
        else:
            print ev

    def _handle_focus(self):
        self.target = self.X.GetInputFocus().reply().focus
        # if window.WM_CLASS in ('Gvim', 'urxvt')
        if self.grab_window != self.target:
            self._ungrabkey()
            self._grabkey()

    def _new_sequence(self,ev):
        assert isinstance(ev, KeyPressEvent)

        #Trust me, this is neccessary 
        key = self.keycode_to_keysym(ev.detail,0)
        if key not in self.grabExclude:
            self.kbdgrab = True
            self.X.GrabKeyboard(True, self.grab_window,X.CurrentTime,xproto.GrabMode.Sync, xproto.GrabMode.Sync).reply()
        #self.on_sequence_new(ev.detail,ev.state,ev.time)
        
        if self.reciever.on_new_sequence(ev.detail,ev.state):
            self.state = GRABBED
        else:
            self.state = PASS_THRU

    def _check_end_seq(self):
        assert self.pressed >=0
        if self.pressed == 0:
            self.state = IDLE
            if self.kbdgrab:
                self.X.UngrabKeyboard(X.CurrentTime)
            if self.should_pause:
                self._ungrabkey()
                self.should_pause = False

    def _slow_poll(self):
        ev = self.conn.poll_for_event()
        if ev is None:
            time.sleep(1e-3)
            ev = self.conn.poll_for_event()
        return ev

    def _sequence_event(self,ev):
        grab = ( self.state == GRABBED )
        if not grab: self._fwd_event(ev)
        if  isinstance(ev, KeyPressEvent):
            self.pressed += 1
            if grab: self.reciever.on_press(ev.detail,ev.state,ev.time,self.pressed)
        else:
            ev2 = self._slow_poll()
            if ev2 != None:
                if isinstance(ev2, KeyPressEvent) and ev2.time == ev.time and ev2.detail == ev.detail:
                    if grab:
                        self.reciever.on_repeat(ev.detail,ev.state,ev.time)
                    else:
                        self._fwd_event(ev2)
                    return

            self.pressed -= 1
            self._check_end_seq()
            # on_release might set state
            if grab: self.reciever.on_release(ev.detail,ev.state,ev.time,self.pressed)
            if ev2 is not None:
                self._handle_event(ev2)

    def send_event(self,ev,window=None):
        if window is None:
            window = self.grab_window
        self.X.SendEvent(True,window,0,ev)

    def _fwd_event(self,ev):
        typeof = typemap[type(ev)] 
        ev = xKeyEvent(
            typeof = typeof,
            seq = 0,
            time = ev.time,
            root = self.root,
            window = self.grab_window,
            same_screen = 0, child = X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = ev.state,
            detail = ev.detail
            )
        self.send_event(ev)

    def pause(self):
        if self.state == IDLE:
            self._ungrabkey()
        else:
            self.should_pause = True
        
 
    def fake_event(self,typeof,keycode,shift_state=0,window=None):
        #whatif window == root, possible?
        if window is None:
            window = self.target
        typeof = typemap.get(typeof,typeof)
        ev = xKeyEvent(
            typeof = typeof,
            seq = 0,
            time = int(time.time()),
            root = self.root,
            window = window,
            same_screen = 0, child = X.NONE,
            root_x = 0, root_y = 0, event_x = 0, event_y = 0,
            state = shift_state,
            detail = keycode
            )
        self.send_event(ev,window)
    def fake_stroke(self,keycode,shift_state=0,window=None):
        self.fake_event(2,keycode,shift_state,window)
        self.fake_event(3,keycode,shift_state,window)

    #TODO: stop NIH:ing, use libxkbcommon, or something else sanity-preserving 
    def _update_keymap(self):
        setup = self.conn.get_setup()
        self.min_keycode = setup.min_keycode  
        self.max_keycode = setup.max_keycode  
        #SRSLY, X?
        self.keymap = self.X.GetKeyboardMapping(self.min_keycode, self.max_keycode - self.min_keycode + 1).reply()

    def keycode_to_keysym(self,keycode,state):
        stride = self.keymap.keysyms_per_keycode
        mn = self.min_keycode
        ind = (keycode - mn) * stride + state_to_level(state)
        return self.keymap.keysyms[ind]

    def lookup_keysym(self,keysym):
        if isinstance(keysym,basestring):
            keysym,ks = XK.string_to_keysym(keysym), keysym
            if keysym == 0:
                raise KeyError(ks)
        stride = self.keymap.keysyms_per_keycode
        mn = self.min_keycode
        keymap = self.keymap.keysyms
        indicies = [i for i, x in enumerate(keymap) if x == keysym]
        pairs = [ ( (i/stride)+mn, level_to_state(i%stride)) for i in indicies]
        pairs.sort(key=lambda x: x[1])
        return pairs

    def lookup_char(self,ch):
        return self.lookup_keysym(char_to_keysym(ch))

    #FIXME: we might want to send chars not mapped on keyboard
    def send_key(self,char):
        pass
        #keysym = XK.string_to_keysym(char)
        #keycode = self.display.keysym_to_keycode(keysym)
        keycode = 10 #FIXME
        self.fake_event(KeyPressEvent, keycode,window=self.target)
        self.fake_event(KeyReleaseEvent, keycode,window=self.target)

def char_to_keysym(ch):
    ucs = ord(ch)
    if 0x20 <= ucs < 0x80 or 0xa0 <= ucs < 0x0100:
        return ucs

# In the general case, this is of course ALL WRONG
def level_to_state(lvl):
    return (lvl&1) + bool(lvl& 4)*0x80

def state_to_level(state):
    return state&1 + bool(state& 0x80)*4

class Test:
    def run(self):
        self.kb = KeyboardGrabber(self)
        self.kb.run()
    # these are for testing
    def on_new_sequence(self,keycode,state):
        print "NEU", keycode, state 
        return keycode != 108

    def on_press(self,keycode,state,time,pressed):
        print "PRESS", keycode, state, pressed

    def on_release(self,keycode,state,time,pressed):
        print "RELEASE", keycode, state, pressed
        if keycode == 10:
            self.kb.send_key('1')
        sym0 = self.kb.keycode_to_keysym(keycode,0)
        if sym0 == XK.XK_Escape:
            raise KeyboardInterrupt

    def on_repeat(self,keycode,state,time):
        #print "REPEAT", ev
        pass



def xKeyEvent(typeof,detail,seq,time, root, window, child, root_x, root_y, event_x, event_y, state, same_screen):
    return struct.pack('BBhIIIIhhhhHBx', typeof,detail,seq,time, root, window, child, root_x, root_y, event_x, event_y, state, same_screen)

if __name__ == "__main__":
    t =Test()
    t.run()
