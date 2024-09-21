local models = ...

-- Create a new buffer and window for the model selection
local buf = vim.api.nvim_create_buf(false, true)
local width = 60
local height = 15
local row = math.floor((vim.o.lines - height) / 2) - 1
local col = math.floor((vim.o.columns - width) / 2)
local opts = {
    relative = 'editor',
    width = width,
    height = height,
    row = row > 0 and row or 0,
    col = col > 0 and col or 0,
    style = 'minimal',
    border = 'rounded'
}
local win = vim.api.nvim_open_win(buf, true, opts)

-- Set up the buffer and window
vim.api.nvim_buf_set_option(buf, 'bufhidden', 'wipe')
vim.api.nvim_win_set_option(win, 'cursorline', true)
vim.api.nvim_buf_set_option(buf, 'modifiable', true)

-- Initial display: Search prompt and full model list
local input = ''

local function render()
    vim.api.nvim_buf_set_option(buf, 'modifiable', true)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, {})  -- Clear buffer

    -- Insert the search prompt
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, {"Search: " .. input})

    -- Filter models based on input
    local filtered = {}
    for _, model in ipairs(models) do
        if string.find(string.lower(model), string.lower(input)) then
            table.insert(filtered, model)
        end
    end

    -- Insert filtered models
    if #filtered == 0 then
        table.insert(filtered, "(No matching models)")
    end
    vim.api.nvim_buf_set_lines(buf, 1, -1, false, filtered)
    vim.api.nvim_buf_set_option(buf, 'modifiable', false)

    -- Move cursor to the search input line
    vim.api.nvim_win_set_cursor(win, {1, #("Search: " .. input)})
end

render()

-- Function to close the window
function close_window()
    vim.api.nvim_win_close(win, true)
end

-- Function to select the model
function select_model()
    local cursor = vim.api.nvim_win_get_cursor(win)
    local line_number = cursor[1]
    if line_number == 1 then
        -- Don't allow selecting the search prompt
        return
    end
    local selected_model = vim.api.nvim_buf_get_lines(buf, line_number - 1, line_number, false)[1]
    if selected_model and selected_model ~= "(No matching models)" then
        close_window()
        vim.fn.LLMModelSelected(selected_model)
    end
end

-- Function to handle backspace
function backspace()
    if #input > 0 then
        input = input:sub(1, -2)
        render()
    end
end

-- Function to handle printable characters
function handle_char(char)
    -- Only handle printable characters (ASCII 32-126)
    if char:match("^%c$") then
        return
    end
    input = input .. char
    render()
end

-- Key mappings
vim.api.nvim_buf_set_keymap(buf, 'n', '<Esc>', ':lua close_window()<CR>', {nowait = true, noremap = true, silent = true})
vim.api.nvim_buf_set_keymap(buf, 'n', '<CR>', ':lua select_model()<CR>', {nowait = true, noremap = true, silent = true})
vim.api.nvim_buf_set_keymap(buf, 'n', '<BS>', ':lua backspace()<CR>', {nowait = true, noremap = true, silent = true})

-- Map all printable characters
for i = 32, 126 do
    local char = string.char(i)
    vim.api.nvim_buf_set_keymap(buf, 'n', char, ':lua handle_char("'..char..'")<CR>', {nowait = true, noremap = true, silent = true})
end

-- Optional: Map arrow keys for navigation
vim.api.nvim_buf_set_keymap(buf, 'n', '<Up>', '<Up>', {nowait = true, noremap = true, silent = true})
vim.api.nvim_buf_set_keymap(buf, 'n', '<Down>', '<Down>', {nowait = true, noremap = true, silent = true})
