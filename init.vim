" Decent ones: koehler evening sorbet torte elflord sorbet wildcharm
" colorscheme koehler
set clipboard=unnamedplus

set nohlsearch
set smartindent
set autoindent
set expandtab
autocmd FileType javascript setlocal shiftwidth=2 softtabstop=2
au BufRead,BufNewFile *.vert set filetype=c
au BufRead,BufNewFile *.frag set filetype=c

" Background matches
colorscheme vim

" My thing
nnoremap <leader>hw :call HelloWrite()<CR>

" In normal mode, clear register 's' and call LLMResponse
nnoremap <leader>l :let @s=""<CR>:call LLMResponse()<CR>

" In visual mode, yank selection into register 's' and call LLMResponse
xnoremap <leader>l "sy:call LLMResponse()<CR>

