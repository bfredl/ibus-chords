  python << EOT
import vim
import ibus
def kc_ic_get():
    from dbus.exceptions import DBusException
    bus = ibus.Bus()
    try:
        return ibus.InputContext(bus, bus.current_input_contxt())
    except DBusException:
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
