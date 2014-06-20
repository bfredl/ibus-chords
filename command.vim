python << EOT
import vim
from gi.repository import IBus
from functools import partial
try:
    chordmap
except:
    chordmap = {}

def kc_ic_get():
    bus = IBus.Bus()
    try:
        return IBus.InputContext.get_input_context(bus.current_input_context(),bus.get_connection())
    except KeyError: #FIXME: correct error
        return None

def kc_magic(k,v):
    ic = kc_ic_get()
    if ic is None: return
    ic.process_key_event(ord(v),k+512-8,0)
    ic.process_key_event(ord(v),k+512-8,1<<30)

Kc_set_mode = partial(kc_magic, 0)
def Kc_insert():
    kc_magic(0,'i')
    try:
        chmap = vim.eval('b:chordmap')
    except:
        ft = vim.eval('&ft')
        chmap = chordmap.get(ft, None)
    if chmap: kc_magic(1,chmap)
EOT

augroup KCCommand
    au!
    au VimEnter * python Kc_set_mode('n')
    au InsertEnter * python Kc_insert()
    au InsertLeave * python Kc_set_mode('n')
    au VimLeave * python Kc_set_mode('e')
    au FocusGained * python Kc_set_mode('n')
augroup END
