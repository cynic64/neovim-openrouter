" Decent ones: koehler evening sorbet torte elflord sorbet wildcharm
" colorscheme koehler
set ts=4 sw=4
let mapleader = " "
let maplocalleader = " "
set clipboard=unnamedplus

set nohlsearch
set smartindent
set autoindent
set expandtab
autocmd FileType javascript setlocal shiftwidth=2 softtabstop=2
au BufRead,BufNewFile *.vert set filetype=c
au BufRead,BufNewFile *.frag set filetype=c

" LLM stuff
" In normal mode, yank entire buffer into register 's'
nnoremap <leader><space> :%y s<CR>:call LLMResponse()<CR>

" Clear buffer, then open llm
nnoremap <leader>c :let @s=""<CR>:call LLMResponse()<CR>

" In visual mode, yank selection into register 's'
xnoremap <leader><space> "sy:call LLMResponse()<CR>
