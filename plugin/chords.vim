python3 << EOT
import vim

# TODO: this belongs in an rplugin

try:
    import zmq
    haszmq = True
except ImportError:
    haszmq = False

if haszmq:
    import os, sys
    ctx = zmq.Context.instance()
    rtd = os.environ["XDG_RUNTIME_DIR"]
    s = ctx.socket(zmq.PUSH)
    s.connect("ipc://{}/chords".format(rtd))
    def Kc_set_mode(*args):
        msg = ["set_mode"] + list(args)
        s.send_json(msg)
else:
    def Kc_set_mode(*args):
        pass

def Kc_insert():
    if int(vim.eval('exists("b:chordmap")')):
        chmap = vim.eval('b:chordmap')
    else:
        chmap = vim.eval('&ft')
    Kc_set_mode('i', chmap)
EOT

augroup KCCommand
    au!
    au VimEnter * py3 Kc_set_mode('n')
    au InsertEnter * py3 Kc_insert()
    au InsertLeave * py3 Kc_set_mode('n')
    au VimLeave * py3 Kc_set_mode('')
    au FocusGained * py3 Kc_set_mode('n')
augroup END

function! s:consume(nam)
    let a = nr2char(getchar())
    let b = nr2char(getchar())
    echo "Invalid ". a:nam .": " . a . b
    return ''
endfunction

map ×× <Plug>ch:
map ÷÷ <Plug>CH:
map <Plug>ch: :call <SID>consume('chord')<CR>
map <Plug>CH: :call <SID>consume('HCHORD')<CR>

map! ×× <Plug>ch:
map! ÷÷ <Plug>CH:
map! <Plug>ch: <c-r>=<SID>consume('chord')<CR>
map! <Plug>CH: <c-r>=<SID>consume('HCHORD')<CR>

if has('nvim')
    tmap ×× <Plug>ch:
    tmap ÷÷ <Plug>CH:
    tmap <expr> <Plug>ch: <SID>consume('chord')
    tmap <expr> <Plug>CH: <SID>consume('HCHORD')
endif

