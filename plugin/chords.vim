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
    def Kc_sendjson(msg):
        s.send_json(msg)

else:
    def Kc_sendjson(msg):
        pass

EOT

let g:kc_current_msg = []
let g:kc_mode_stack = []

function! Kc_set_mode(mode, ...)
  let msg = ["set_mode", a:mode]
  if a:mode ==# 'i'
    if a:0 > 0
      let chmap = a:1
    else
      if exists("b:chordmap")
        let chmap = b:chordmap
      else
        let chmap = &ft
      end
    end
    call add(msg, chmap)
  end
  let g:kc_current_msg = msg
  py3 Kc_sendjson(vim.vars['kc_current_msg'])
endfunction


function! Kc_push_mode(...)
  call add(g:kc_mode_stack, g:kc_current_msg)
  call call("Kc_set_mode", a:000)
endfunction

function! Kc_pop_mode()
  let g:kc_current_msg = remove(g:kc_mode_stack, -1)
  py3 Kc_sendjson(vim.vars['kc_current_msg'])
endfunction

augroup KCCommand
    au!
    au VimEnter * call Kc_set_mode('n')
    au InsertEnter * call Kc_set_mode('i')
    au InsertLeave * call Kc_set_mode('n')
    au VimLeave * call Kc_set_mode('')
    au FocusGained * call Kc_set_mode('n')
    if exists("##CmdlineEnter")
        " set i but ignore keymaps
        au CmdlineEnter * call Kc_push_mode('i', 'vim')
        " TODO: use a stack to restore actual keymap
        au CmdlineLeave * call Kc_pop_mode()
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
map <Plug>ch: :<c-u>call <SID>consume('chord')<CR>
map <Plug>CH: :<c-u>call <SID>consume('HCHORD')<CR>

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

