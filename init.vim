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
nnoremap <leader>lr :call LLMResponse()<CR>
