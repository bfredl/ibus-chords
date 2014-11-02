#!/usr/bin/env python3
# encoding: utf8

# Based on ibus-tmpl - The Input Bus template project, which is
# Copyright (c) 2007-2014 Peng Huang <shawn.p.huang@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# for python2
from __future__ import print_function

from gi.repository import IBus
from gi.repository import GLib, GObject, Gdk

import os
import sys
import getopt
import locale
import time

from keysym import desc_to_keysym, keysym_desc
IDLE = 0
GRABBED = 1
PASS_THRU = 2

def set_proc_name(newname):
    from ctypes import cdll, byref, create_string_buffer
    libc = cdll.LoadLibrary('libc.so.6')
    buff = create_string_buffer(len(newname)+1)
    buff.value = newname.encode()
    libc.prctl(15, byref(buff), 0, 0, 0)


class BaseEngine(IBus.Engine):
    __gtype_name__ = 'BaseEngine'

    def __init__(self):
        super(BaseEngine, self).__init__()
        self.__is_invalidate = False
        self.initialize()
        self.__lookup_table = IBus.LookupTable.new(10, 0, True, True)
        self.__prop_list = IBus.PropList()
        self.__prop_list.append(IBus.Property(key="command-mode", icon="ibus-local"))
        #override this in subclass
        self.target = Test(self)
        self.keymap = Gdk.Keymap.get_default()
        self.keymap.connect('keys_changed', lambda *a: self.target.on_keymap_change())

        #FIXME: this is not guaranteed by the X standard
        # but in X.org it seems to always be 8
        self.min_keycode = 8

        self.vimfix = False

    def initialize(self):
        self.state = IDLE
        self.pressed = set()

    def do_process_key_event(self, keyval, keycode, state):
        t = time.time()*1000 #msec
        #print("process_key_event(%04x, %d, %04x)" % (keyval, keycode, state))
        #print(self.state)
        is_press = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        state &= ~IBus.ModifierType.RELEASE_MASK
        
        # the IBus devs apparently forgot this:
        keycode += self.min_keycode

        if is_press:
            if keycode in self.pressed:
                print("SPURIOUS press", keycode)
            self.pressed.add(keycode)
        else:
            try:
                self.pressed.remove(keycode)
            except KeyError: # get rid of spurious keyReleases
                print("SPURIOUS release", keycode)
                return False

        if self.state == IDLE:
            assert is_press
            if self.target.on_new_sequence(keyval,keycode,state, t):
                self.state = GRABBED
            else:
                self.state = PASS_THRU

        grab = (self.state == GRABBED)
        if not self.pressed:
            self.state = IDLE
        #print(self.state, self.pressed)

        if grab:
            if is_press:
                return self.target.on_press(keyval, keycode, state,t,len(self.pressed))
            else:
                return self.target.on_release(keyval, keycode, state,t,len(self.pressed))
        else:
            return False


    def show_preedit(self, string):
        self.__preedit_string = string
        self.__update()


    def commit_string(self, text):
        self.commit_text(IBus.Text.new_from_string(text))
        self.__preedit_string = ""
        self.__update()

    def get_keyval(self, keycode, state):
            ok, keyval, _, _, _ = self.keymap.translate_keyboard_state(keycode, Gdk.ModifierType(state), 0)
            return keyval

    def fake_stroke(self, keyval, keycode, state):
        if keyval is None:
            ok, keyval, _, _, _ = self.keymap.translate_keyboard_state(keycode, Gdk.ModifierType(state), 0)
            if not ok: 
                print( 'ERROR')

        # le sigh...
        keycode -= self.min_keycode
        self.forward_key_event(keyval, keycode, state)
        self.forward_key_event(keyval, keycode, state | IBus.ModifierType.RELEASE_MASK)

    def __update(self):
        preedit_len = len(self.__preedit_string)
        attrs = IBus.AttrList()
        text = IBus.Text.new_from_string(self.__preedit_string)
        text.set_attributes(attrs)
        #self.update_auxiliary_text(text, preedit_len > 0)

        #attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE,
        #       IBus.AttrUnderline.SINGLE, 0, preedit_len))
        text = IBus.Text.new_from_string(self.__preedit_string)
        text.set_attributes(attrs)
        #This is broken in latest Gvim (normal mode interprets preedit as commands => epic chaos)
        if self.vimfix:
            self.update_auxiliary_text(text, preedit_len > 0)
            self.hide_preedit_text()
        else:
            self.update_preedit_text_with_mode(text, preedit_len, preedit_len > 0, IBus.PreeditFocusMode.CLEAR)
            self.hide_auxiliary_text()
        self.__is_invalidate = False

    def lookup_keysym(self,keyval):
        if isinstance(keyval,str):
            keyval,ks = desc_to_keysym(keyval), keyval
            if keyval == 0:
                raise KeyError(ks)
        ok, res = self.keymap.get_entries_for_keyval(keyval)
        if not ok: return []
        pairs = [(r.keycode, r.level) for r in res if r.group == 0]
        pairs.sort(key=lambda x: x[1])
        return pairs

    def schedule(self,msecs, callback):
        GLib.timeout_add(msecs, callback)

    def do_focus_in(self):
        print('onfocus')
        #TODO: unbreak gvim instead
        os.system("xprop -id `xdotool getwindowfocus` WM_CLASS")
        self.vimfix = (os.system("xprop -id `xdotool getwindowfocus` WM_CLASS|grep Gvim > /dev/null") == 0)
        chfix = os.system("xprop -id `xdotool getwindowfocus` WM_CLASS|grep chromium > /dev/null") == 0
        if not self.vimfix:
            #gvim sometimes emits a TONNE of focus/defocus events
            #right after entering insert mode; ignore these
            self.target.on_reset()
        self.target.set_quiet(chfix)
        self.register_properties(self.__prop_list)
        self.initialize()

    def do_focus_out(self):
        print('on unfocus')
        pass

    def do_reset(self):
        print('onreset')
        if not self.vimfix:
            self.target.on_reset()

    def do_property_activate(self, prop_name, state):
        print("PropertyActivate(%s)" % prop_name)
        if prop_name == "command-mode":
            pass

class ChordEngine(BaseEngine):
    __gtype_name__ = 'ChordEngine'
    def __init__(self):
        super(ChordEngine, self).__init__()
        try:
            from KeyboardChorder import KeyboardChorder
            self.target = KeyboardChorder(self)
        except Exception:
            import traceback
            traceback.print_exc()
            sys.exit(111)

class Test:
    def __init__(self, im):
        self.im = im
        self.string = ''

    def on_new_sequence(self, keyval, keycode, state, time):
        print( "NEU", keyval, keycode, state )
        if keyval == ord('q'): sys.exit()
        return islatin(keyval) and not  state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK)

    def on_press(self, keyval, keycode, state, time, pressed):
        print( "PRESS", keyval, keycode, state, pressed)
        #if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK) == 0:
        if islatin(keyval):
            self.string += chr(keyval)
        self.im.show_preedit(self.string)
        return True

    def on_release(self, keyval, keycode, state, time, pressed):
        print( "release", keyval, keycode, state, pressed)
        if islatin(keyval):
            self.im.commit_string(self.string)
            self.string = ''
            return True
        return True

class IMApp:
    def __init__(self, exec_by_ibus):
        engine_name = "KeyboardChorder" if exec_by_ibus else "KeyboardChorder dbg"
        self.__component = \
                IBus.Component.new("com.github.bfredl.KeyboardChorder",
                                   "KeyboardChorder IBus component",
                                   "0.0.0",
                                   "MIT",
                                   "Björn Linse <bjorn.linse@gmail.com> ",
                                   "http://bfredl.github.io",
                                   "/usr/bin/FIXME",
                                   "ibus-FIXME")
        engine = IBus.EngineDesc.new("KeyboardChorder",
                                     engine_name,
                                     "Crazy keyboard chords",
                                     "en",
                                     "MIT",
                                     "Björn Linse <bjorn.linse@gmail.com> ",
                                     "",
                                     "se")
        self.__component.add_engine(engine)
        self.__mainloop = GLib.MainLoop()
        self.__bus = IBus.Bus()
        self.__bus.connect("disconnected", self.__bus_disconnected_cb)
        self.__factory = IBus.Factory.new(self.__bus.get_connection())
        self.__factory.add_engine("KeyboardChorder",
                GObject.type_from_name("ChordEngine"))
        if exec_by_ibus:
            self.__bus.request_name("com.github.bfredl.KeyboardChorder", 0)
        else:
            self.__bus.register_component(self.__component)
            self.__bus.set_global_engine_async(
                    "KeyboardChorder", -1, None, None, None)

    def run(self):
        self.__mainloop.run()

    def __bus_disconnected_cb(self, bus):
        self.__mainloop.quit()


def launch_engine(exec_by_ibus):
    IBus.init()
    IMApp(exec_by_ibus).run()

def print_help(v = 0):
    print("-i, --ibus             executed by IBus.")
    print("-h, --help             show this message.")
    print("-d, --daemonize        daemonize ibus")
    sys.exit(v)

def main():
    try:
        locale.setlocale(locale.LC_ALL, "")
    except:
        pass

    exec_by_ibus = False
    daemonize = False

    shortopt = "ihd"
    longopt = ["ibus", "help", "daemonize"]

    try:
        opts, args = getopt.getopt(sys.argv[1:], shortopt, longopt)
    except getopt.GetoptError as err:
        print_help(1)

    for o, a in opts:
        if o in ("-h", "--help"):
            print_help(sys.stdout)
        elif o in ("-d", "--daemonize"):
            daemonize = True
        elif o in ("-i", "--ibus"):
            exec_by_ibus = True
        else:
            sys.stderr.write("Unknown argument: %s\n" % o)
            print_help(1)

    if daemonize:
        if os.fork():
            sys.exit()

    launch_engine(exec_by_ibus)

if __name__ == "__main__":
    set_proc_name('keyboard-chorder')
    main()
