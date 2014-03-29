# vim:set et sts=4 sw=4:
# encoding: utf8
# ibus-tmpl - The Input Bus template project
#
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
from gi.repository import GLib
from gi.repository import GObject

import os
import sys
import getopt
import locale

keysyms = IBus

class ChordEngine(IBus.Engine):
    __gtype_name__ = 'ChordEngine'

    def __init__(self):
        super(ChordEngine, self).__init__()
        self.__is_invalidate = False
        self.__preedit_string = ""
        self.__lookup_table = IBus.LookupTable.new(10, 0, True, True)
        self.__prop_list = IBus.PropList()
        self.__prop_list.append(IBus.Property(key="test", icon="ibus-local"))
        print("Create ChordEngine OK")

    def do_process_key_event(self, keyval, keycode, state):
        print("process_key_event(%04x, %04x, %04x)" % (keyval, keycode, state))
        # ignore key release events
        is_press = ((state & IBus.ModifierType.RELEASE_MASK) == 0)
        if is_press:
            return self.on_key_press(keyval, keycode, state)
        else:
            return self.on_key_release(keyval, keycode, state)

        if self.__preedit_string:
            if keyval == keysyms.Return:
                self.__commit_string(self.__preedit_string)
                return True
            elif keyval == keysyms.Escape:
                self.__preedit_string = ""
                self.__update()
                return True
            elif keyval == keysyms.BackSpace:
                self.__preedit_string = self.__preedit_string[:-1]
                self.__invalidate()
                return True
            elif keyval == keysyms.space:
                if self.__lookup_table.get_number_of_candidates() > 0:
                    self.__commit_string(self.__lookup_table.get_current_candidate().text)
                else:
                    self.__commit_string(self.__preedit_string)
                return False
            elif keyval >= 49 and keyval <= 57:
                #keyval >= keysyms._1 and keyval <= keysyms._9
                index = keyval - keysyms._1
                candidates = self.__lookup_table.get_canidates_in_current_page()
                if index >= len(candidates):
                    return False
                candidate = candidates[index].text
                self.__commit_string(candidate)
                return True
        if keyval in range(keysyms.a, keysyms.z + 1) or \
            keyval in range(keysyms.A, keysyms.Z + 1):
            if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK) == 0:
                self.__preedit_string += chr(keyval)
                self.__invalidate()
                return True
        else:
            if keyval < 128 and self.__preedit_string:
                self.__commit_string(self.__preedit_string)

        return False

    def on_key_press(self, keyval, keycode, state):
        islat =  0x20 <= keyval < 0x80 or 0xa0 <= keyval < 0x0100
        if islat:
            if keyval == ord('q'): sys.exit()
            #if state & (IBus.ModifierType.CONTROL_MASK | IBus.ModifierType.MOD1_MASK) == 0:
            self.__preedit_string += chr(keyval)
            self.__invalidate()
            return True
        return False

    def on_key_release(self, keyval, keycode, state):
        islat =  0x20 <= keyval < 0x80 or 0xa0 <= keyval < 0x0100
        if islat:
            self.__commit_string(self.__preedit_string)
            return True
        return False

    def __invalidate(self):
        if self.__is_invalidate:
            return
        self.__is_invalidate = True
        GLib.idle_add(self.__update)

    def __commit_string(self, text):
        self.commit_text(IBus.Text.new_from_string(text))
        self.__preedit_string = ""
        self.__update()

    def __update(self):
        preedit_len = len(self.__preedit_string)
        attrs = IBus.AttrList()
        self.__lookup_table.clear()
        if False:
            if not self.__dict.check(self.__preedit_string):
                attrs.append(IBus.Attribute.new(IBus.AttrType.FOREGROUND,
                        0xff0000, 0, preedit_len))
                for text in self.__dict.suggest(self.__preedit_string):
                    self.__lookup_table.append_candidate(IBus.Text.new_from_string(text))
        text = IBus.Text.new_from_string(self.__preedit_string)
        text.set_attributes(attrs)
        #self.update_auxiliary_text(text, preedit_len > 0)

        #attrs.append(IBus.Attribute.new(IBus.AttrType.UNDERLINE,
        #       IBus.AttrUnderline.SINGLE, 0, preedit_len))
        text = IBus.Text.new_from_string(self.__preedit_string)
        text.set_attributes(attrs)
        self.update_preedit_text(text, preedit_len, preedit_len > 0)
        self.__update_lookup_table()
        self.__is_invalidate = False

    def __update_lookup_table(self):
        visible = self.__lookup_table.get_number_of_candidates() > 0
        self.update_lookup_table(self.__lookup_table, visible)


    def do_focus_in(self):
        print("focus_in")
        self.register_properties(self.__prop_list)

    def do_focus_out(self):
        print("focus_out")

    def do_reset(self):
        print("reset")

    def do_property_activate(self, prop_name):
        print("PropertyActivate(%s)" % prop_name)


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
    main()