" Decent ones: koehler evening sorbet torte elflord sorbet wildcharm
" colorscheme koehler
set ts=4 sw=4
let mapleader = " "
let maplocalleader = " "
set clipboard=unnamedplus

source $HOME/.config/nvim/home.vim

set nohlsearch
set smartindent
set autoindent
set expandtab
autocmd FileType javascript setlocal shiftwidth=2 softtabstop=2
au BufRead,BufNewFile *.vert set filetype=c
au BufRead,BufNewFile *.frag set filetype=c

" Yank whole buffer
nnoremap <leader><space> :%y s<CR>:call LLMResponse()<CR>
" Yank nothing
nnoremap <leader>c :let @s=""<CR>:call LLMResponse()<CR>
" Yank selection in visual mode
xnoremap <leader><space> "sy:call LLMResponse()<CR>
