python << EOT
import vim

# TODO: this belongs in a module
import zmq
import os, sys
ctx = zmq.Context.instance()
rtd = os.environ["XDG_RUNTIME_DIR"]
s = ctx.socket(zmq.PUSH)
s.connect("ipc://{}/chords".format(rtd))
def Kc_set_mode(*args):
    msg = ["set_mode"] + list(args)
    s.send_json(msg)

def Kc_insert():
    if int(vim.eval('exists("b:chordmap")')):
        chmap = vim.eval('b:chordmap')
    else:
        chmap = vim.eval('&ft')
    Kc_set_mode('i', chmap)
EOT

augroup KCCommand
    au!
    au VimEnter * python Kc_set_mode('n')
    au InsertEnter * python Kc_insert()
    au InsertLeave * python Kc_set_mode('n')
    au VimLeave * python Kc_set_mode('')
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

