python << EOT
import vim
from gi.repository import IBus
from functools import partial
from contextlib import contextmanager
try:
    chordmap
except:
    chordmap = {}

ibus = IBus.Bus()

@contextmanager
def kc_ic_get():
    try:
        ic = IBus.InputContext.get_input_context(ibus.current_input_context(),ibus.get_connection())
        yield ic
        ic.destroy()
    except KeyError: #FIXME: correct error
        yield None

def kc_magic(k,v):
    with kc_ic_get() as ic:
        if ic is None: return
        ic.process_key_event(ord(v),k+512-8,0)
        ic.process_key_event(ord(v),k+512-8,1<<30)

Kc_set_mode = partial(kc_magic, 0)
Kc_set_cmap = partial(kc_magic, 1)
def Kc_insert():
    kc_magic(0,'i')
    try:
        chmap = vim.eval('b:chordmap')
    except:
        ft = vim.eval('&ft')
        chmap = chordmap.get(ft, None)
    if chmap: 
        Kc_set_cmap(chmap)
    else:
        Kc_set_mode('i')
EOT

augroup KCCommand
    au!
    au VimEnter * python Kc_set_mode('n')
    au InsertEnter * python Kc_insert()
    au InsertLeave * python Kc_set_mode('n')
    au VimLeave * python Kc_set_mode('e')
    au FocusGained * python Kc_set_mode('n')
augroup END

function! s:consume(nam)
    let a = nr2char(getchar())
    let b = nr2char(getchar())
    echo "Invalid ". a:nam .": " . a . b
    return ''
endfunction
map ×× <Plug>ch:
map ÷÷ <Plug>CH:
map! ×× <Plug>ch:
map! ÷÷ <Plug>CH:
map <Plug>ch: :call <SID>consume('chord')<CR>
map <Plug>CH: :call <SID>consume('HCHORD')<CR>
map! <Plug>ch: <c-r>=<SID>consume('chord')<CR>
map! <Plug>CH: <c-r>=<SID>consume('HCHORD')<CR>

