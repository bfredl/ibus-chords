# -*- coding: utf-8 -*-
from xkeyboard import KeyboardGrabber
from Xlib import XK
from operator import or_
from collections import namedtuple

SHIFT = 0x01
CTRL = 0x04
LEVEL3 = 0x80

dbg = True

Press = namedtuple('Press', ['keyval','keycode','state','time'])
class KeyboardChorder(object):
    def __init__(self, im):
        self.im = im
        self.modThreshold = 200
        self.modThreshold2 = 300
        self.chordTreshold = 2.0

        self.configure()

    def configure(self):
        #TODO this belongs in 'config' repo where the keymap is
        chords = {
            'eh': 'F',
            'ut': 'f',
            'as': ' = ',
            'is': ' == ',
            '\'c': '\': \'',
            'oe': ' += ',
            'ht': '()',
            'ac': '0',
            'oc': '1',
            'ec': '2',
            'uc': '3',
            ',c': '4',
            '.c': '5',
            'pc': '6',
            'qc': '7',
            'jc': '8',
            'kc': '9',
            'a0': self.pause,
            'or': u'ö', 'ocr': u'Ö',
            'er': u'ä', 'ecr': u'Ä',
            'ar': u'å', 'acr': u'Å',
            'el': '} else {',
            ' :': ';',
            'uh': '{',
            'et': '}',
            'jh': '{{{',
            'kh': '}}}',
        }

        modmap = {
            'HOLD': SHIFT,
            'space': LEVEL3,
            'Escape': LEVEL3 | SHIFT,
            'colon': CTRL
        }
        ignore = { 'BackSpace', 'Control_L', 'Shift_L', 0xFE03, 'Alt_L'}
        ch_char = u'ö'

        def code_s(s):
            if s == 'HOLD': return s
            syms = self.im.lookup_keysym(s)
            return syms[0][0] if syms else s

        self.remap = {}
        #FIXME: represent state with keysyms instead
        for desc, val in chords.items():
            chord = []
            for ch in desc:
                chord.append(code_s(ch))
            self.remap[tuple(sorted(chord))] = val 
        print self.remap

        self.modmap = { code_s(s) or s: mod for s, mod in modmap.iteritems()}
        self.ignore = { code_s(s) for s in ignore}
        self.ignore.add(108)
        self.ch_char  = ch_char

    def psym(self,val):
        if 0x20 <= val < 0x80 or 0xa0 <= val < 0x0100:
            return chr(val)
        else:
            return val

    def run(self):
        try:
            self.kb.run()
        except KeyboardInterrupt:
            pass

    def pause(self):
        pass
            
    def on_new_sequence(self, keyval, keycode, state, time):
        if keycode in self.ignore:
            return False 
        self.seq = []
        self.down = {}
        self.dead = set()
        self.seq_time = time 
        self.seq_d = False
        self.last_nonchord = 0
        return True

    def on_press(self, keyval, keycode, state, time, pressed):
        p = Press(keyval, keycode, state, time)
        self.down[keycode] = p
        if not self.seq_d:
            self.seq.append(p)
        else:
            self.dead.add(keycode)
        self.last_time = time
        self.update_display()
        if dbg:
            print '+', self.psym(keyval), time-self.seq_time
        return not self.seq_d

    def on_release(self, keyval, keycode,state,time,pressed):
        if dbg:
            print '-', self.psym(keyval), time-self.seq_time
        if keycode in self.dead:
            self.dead.remove(keycode)
            res = []
            dead = ()
        else:
            dead, res = self.get_chord(time,keycode)
            if not dead:
                #TODO: maybe latch 'sequential mode'?
                dead = self.down.keys()
                res = list(self.seq)
                self.seq_d = True
        self.dead.update([k for k in dead if k != keycode])
        self.seq = [p for p in self.seq if p.keycode not in dead]
        del self.down[keycode]
        if res: self.im.show_preedit('')
        if callable(res):
            res()
        elif isinstance(res, basestring):
            self.im.commit_string(res)
        else:
            for p in res:
                self.im.fake_stroke(*p[:3])
        self.last_time = time
        self.update_display()
        return True

    def on_repeat(self, *a):
        pass # (:

    def on_keymap_change(self):
        self.configure()

    def update_display(self):
        if self.down:
            self.im.show_preedit('{} {}'.format(len(self.down),len(self.seq)))
        else:
            self.im.show_preedit('')

    #FIXME: return actions instead for OSD preview
    def get_chord(self,time,keycode):
        nochord = ((), [])
        n = len(self.down)
        times = sorted( p.time for p in self.down.values())
        hold = time - self.last_time >= self.modThreshold
        if len(self.dead) == 0:
            if n == 1 and not hold:
                return nochord
                    
            # risk of conflict with slightly overlapping sequence
            if n == 2 and not hold:
                hold2 = time - times[-2] >= self.modThreshold2
                if time - self.last_nonchord < 120:
                    return nochord
                if keycode == self.seq[0].keycode and not hold2: # ab|ba is always chord
                    print '!hold2'
                    t0, t1 = times[-2:]
                    t2 = time
                    if t2-t1 < (self.chordTreshold)*(t1-t0):
                        return nochord

        chord = tuple(sorted([ p.keycode for p in self.down.values()]))
        print(chord)
        #keysym = self.im.keycode_to_keysym(keycode,0) #[sic]
        if chord in self.remap:
            seq = self.remap[chord]
            return chord, seq

        modmap = self.modmap
        modders = set(chord) &  modmap.viewkeys()
        state = reduce(or_, (modmap[k] for k in modders),0)
        other = set(chord) - modders
        if modders and other:
            #FIXME: not ambigous anymore, fire of 'other' in order in self.seq
            if len(other) == 1:
                keycode = other.pop() 
            elif keycode not in other:
                return chord, []# ambigous: do nothing

            return modders | {keycode}, [(None,keycode,state)]

        if len(chord) == 1:
            keycode, = chord
            self.im.fake_stroke
            return chord, [(None,keycode,modmap['HOLD'])]
        else:
            #FIXME; RETHINK
            print('FAULT')
            return nochord
            self.im.fake_stroke(*self.ch_code)
            for key in chord:
                self.im.fake_stroke(*key)

if __name__ == "__main__":
    import time
    KeyboardChorder().run()
