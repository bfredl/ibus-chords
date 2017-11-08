if !has("python3")
    finish
endif
python3 << EOT
import vim

# TODO: this belongs in an rplugin

try:
    import zmq
    haszmq = True
except ImportError:
    haszmq = False

kc_modemsg = None

if haszmq:
    import os, sys
    ctx = zmq.Context.instance()
    rtd = os.environ["XDG_RUNTIME_DIR"]
    s = ctx.socket(zmq.PUSH)
    s.connect("ipc://{}/chords".format(rtd))
    def Kc_set_mode(mode, chmap=None):
        global kc_modemsg
        msg = ["set_mode", mode]
        if mode == 'i':
            if chmap is None:
                chmap = get_chmap()
            msg.append(chmap)

        kc_modemsg = msg
        s.send_json(msg)
else:
    def Kc_set_mode(*args):
        pass

def get_chmap():
    if int(vim.eval('exists("b:chordmap")')):
        chmap = vim.eval('b:chordmap')
    else:
        chmap = vim.eval('&ft')
    return chmap

modes = []
def Kc_push_mode(*args):
    modes.append(kc_modemsg)
    Kc_set_mode(*args)

def Kc_pop_mode():
    global kc_modemsg
    kc_modemsg = modes.pop()
    if haszmq:
        s.send_json(kc_modemsg)

EOT

augroup KCCommand
    au!
    au VimEnter * py3 Kc_set_mode('n')
    au InsertEnter * py3 Kc_set_mode('i')
    au InsertLeave * py3 Kc_set_mode('n')
    au VimLeave * py3 Kc_set_mode('')
    au FocusGained * py3 Kc_set_mode('n')
    if exists("##CmdlineEnter")
        " set i but ignore keymaps
        au CmdlineEnter * py3 Kc_push_mode('i', 'vim')
        " TODO: use a stack to restore actual keymap
        au CmdlineLeave * py3 Kc_pop_mode()
    end
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

