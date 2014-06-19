python << EOT
import vim
from gi.repository import IBus
def kc_ic_get():
    bus = IBus.Bus()
    try:
        return IBus.InputContext.get_input_context(bus.current_input_context(),bus.get_connection())
    except KeyError: #FIXME: correct error
        return None

def kc_set_mode(mode):
    ic = kc_ic_get()
    if ic is None: return
    ic.process_key_event(ord(mode),512-8,0)
    ic.process_key_event(ord(mode),512-8,1<<30)

EOT

function! Kc_set_mode(mode)
    python kc_set_mode(vim.eval('a:mode'))
endfunction

augroup KCCommand
    au!
    au VimEnter * call Kc_set_mode('n')
    au InsertEnter * call Kc_set_mode('i')
    au InsertLeave * call Kc_set_mode('n')
    au VimLeave * call Kc_set_mode('e')
    au FocusGained * call Kc_set_mode('n')
augroup END
