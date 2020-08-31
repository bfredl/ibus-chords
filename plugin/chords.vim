let g:kc_path = "ipc://".$XDG_RUNTIME_DIR."/chords"

if luaeval("pcall(require,'lzmq')")
  lua <<EOT

  local zmq = require'lzmq'
  local context = assert(zmq.context())
  kc_socket = context:socket(zmq.PUSH)
  kc_socket:connect(vim.api.nvim_get_var("kc_path"))
  kc_sub = context:socket(zmq.SUB)
  kc_sub:connect(vim.api.nvim_get_var("kc_path").."_status")
  kc_sub:setopt_str(zmq.SUBSCRIBE, "")
  lork = vim.api.nvim_get_var("kc_path").."_status"
  kc_laststatus = ""
  function kc_recv()
    if not kc_sub:poll(10) then return nil end
    local msg = kc_sub:recv()
    kc_laststatus = msg
    return msg
  end
  -- TODOß HAIIIb
  -- local thebuf, thewin
  function checkit()
    local msg = kc_recv()
    if msg then
      on_msg(msg)
    end
  end
  function on_msg(msg)
    local m = vim.fn.json_decode(msg)
    if m.kind ~= "cursor" then
      vim.api.nvim_buf_set_lines(thebuf, -1, -1, true, vim.split(vim.inspect(m),'\n',true))
      vim.api.nvim_win_set_cursor(thewin, {vim.api.nvim_buf_line_count(thebuf), 9000})
      vim.cmd "redraw!" -- IIIIH
    end
  end
  function foll()
      if not thebuf then
          thebuf = vim.api.nvim_get_current_buf()
          thewin = vim.api.nvim_get_current_win()
      end
      vim.cmd "call timer_start(10, {i -> v:lua.checkit()}, {'repeat': -1})"
  end
EOT
  function! Kc_send_json(msg)
    call luaeval("kc_socket:send(_A)", json_encode(a:msg))
  endfunction

elseif has("python3")

  python3 << EOT
import vim

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
    def Kc_sendjson(msg):
        s.send_json(msg)

else:
    def Kc_sendjson(msg):
        pass

EOT

  function! Kc_send_json(msg)
    py3 Kc_sendjson(vim.eval('a:msg'))
  endfunction
else
  function! Kc_send_json(msg)
  endfunction
end

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
  call Kc_send_json(msg)
endfunction

function! Kc_push_mode(...)
  call add(g:kc_mode_stack, g:kc_current_msg)
  call call("Kc_set_mode", a:000)
endfunction

function! Kc_pop_mode()
  let g:kc_current_msg = remove(g:kc_mode_stack, -1)
  call Kc_send_json(g:kc_current_msg)
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

