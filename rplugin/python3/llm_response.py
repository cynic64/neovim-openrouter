import pynvim
from core import get_response
import time
import logging
import threading
import os
import re
import textwrap

SYSTEM_PROMPT = """Source code will always be given to you with line numbers,
followed by a `|`, followed by the actual line of source code.

Never include line numbers in the code you output.

If you suggest changes to code you were given, always use
EXACTLY the following format:

--- REPLACE $START_LINE $END_LINE WITH ---
your new code you want to replace the old code with
can be multiple lines
can be more or less lines than the old code!
--- END ---

Replace $START_LINE and $END_LINE with the first and last line you
want to be replaced with your new code. The range is inclusive. Make sure you
get the range exactly right!

You can specify multiple such REPLACE ranges.

If you weren't given any code to base your response off and are starting from
scratch, do

-- REPLACE 0 0 WITH ---
your code here
maybe multiple lines
--- END ---
"""

# model name -> (temperature, top_p)
parameters = {
    "anthropic/claude-3.5-sonnet:beta": (0.7, 0.9),
    "openai/o1-mini": (0.7, 0.95),
    "google/gemini-pro-1.5-exp": (1, 0.9),
    "openai/o1-preview": (1, 1),
}

models = [
    "anthropic/claude-3.5-sonnet:beta",
    "openai/o1-mini",
    "google/gemini-pro-1.5-exp",
    "openai/o1-preview",
]


# Set up logging
logging.basicConfig(
    filename='/tmp/nvim_llm_plugin.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

@pynvim.plugin
class LLMResponsePlugin(object):
    def __init__(self, nvim):
        self.nvim = nvim
        logging.error("LLMResponsePlugin initialized")
        self.conversation_buffer = None  # Store the conversation buffer number
        self.selected_text = None  # Store selected text if any
        self.code_buffer = None  # Store the code buffer number
        self.lua_dir = os.path.dirname(os.path.abspath(__file__))

    @pynvim.function("LLMResponse", sync=False)
    def llm_response(self, args):
        logging.error("llm_response function called")

        # Store the current buffer as the code buffer
        self.code_buffer = self.nvim.current.buffer
        logging.error(f"Code buffer stored: {self.code_buffer.number}")

        # Get the selection from register 's'
        self.selected_text = self.nvim.funcs.getreg('s').rstrip()
        if self.selected_text == '':
            self.selected_text = None
            logging.error("No visual selection detected")
        else:
            # Prepend line numbers to every line
            numbered_lines = []
            for i, line in enumerate(self.selected_text.split("\n")):
                numbered_lines.append(f"{i+1:<5}|{line}")

            numbered_text = "\n".join(numbered_lines)
            self.selected_text = f"```\n{numbered_text}\n```"

            logging.error(f"Selected text: {self.selected_text}")

        # Check if the conversation buffer exists
        if self.conversation_buffer and self.nvim.api.buf_is_valid(self.conversation_buffer):
            # Open the buffer in a new window at the bottom
            buf = self.nvim.buffers[self.conversation_buffer]
            logging.error(f"Reopening existing buffer {buf.number}")
        else:
            # Create a new scratch buffer
            buf = self.nvim.api.create_buf(False, True)
            self.conversation_buffer = buf.number

            # Set buffer options
            self.nvim.api.buf_set_option(buf, 'buftype', 'nofile')
            self.nvim.api.buf_set_option(buf, 'swapfile', False)
            self.nvim.api.buf_set_option(buf, 'bufhidden', 'wipe')

            # Set up buffer-local key mapping to trigger submission and model
            # switching
            self.nvim.api.buf_set_keymap(
                buf.number,
                'n',
                '<leader><space>',
                ':LLMSubmitCommand<CR>',
                {'nowait': True, 'noremap': True, 'silent': True}
            )
            self.nvim.api.buf_set_keymap(
                buf.number,
                'n',
                '<leader>m',
                ':LLMSelectModel<CR>',
                {'nowait': True, 'noremap': True, 'silent': True}
            )
            logging.error(f"Created new buffer {buf.number} for conversation")

        # Open a new window for the buffer at the bottom
        self.nvim.command(f"botright split")
        self.nvim.command(f"buffer {buf.number}")

        # If there is selected text, insert it into the buffer at the end
        if self.selected_text:
            # Get current buffer content
            lines = buf[:]

            # Avoid blank initial line
            if lines and lines[0] == "":
                lines = lines[1:]

            # Split selected text into lines and append
            lines.extend(self.selected_text.split('\n') + [''])
            buf[:] = lines
            logging.error(f"Inserted selected text into buffer")
        # Move the cursor to the end of the buffer
        self.nvim.command('normal! G$')

    @pynvim.command('LLMSubmitCommand', nargs='*', sync=False)
    def llm_submit_command(self, args):
        logging.error("llm_submit_command called")
        self.llm_submit(args)

    def llm_submit(self, args):
        logging.error("llm_submit function called")

        # Get the conversation buffer
        conv_buf = self.nvim.buffers[self.conversation_buffer]

        # Get the text from the buffer
        lines = conv_buf[:]

        logging.error(f"Full conversation from buffer: {lines}")

        # Parse the buffer content into model and messages
        model, messages = self.parse_buffer_content(lines)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

        logging.error(f"Parsed model: {model}")
        logging.error(f"Parsed messages: {messages}")

        # Pass both conversation and code buffers
        threading.Thread(target=self.fetch_and_display, args=(conv_buf, self.code_buffer, model, messages)).start()

    def fetch_and_display(self, conv_buf, code_buf, model, messages):
        logging.error("fetch_and_display function started")
        response_content = ''

        if model is None:
            model = models[0]

        temperature, top_p = parameters[model]

        # Append separator and empty line in the main thread
        def append_separator():
            conv_buf[:] = conv_buf[:] + ['---', '']
            self.nvim.command(f"normal! G$")
            self.nvim.command('redraw')

        self.nvim.async_call(append_separator)

        response_start_idx = None
        # Have to do this through async_call otherwise nvim is unhappy
        def get_response_start_idx():
            nonlocal response_start_idx
            response_start_idx = len(conv_buf[:])

        # Wait to make sure separator gets appended
        time.sleep(0.01)
        self.nvim.async_call(get_response_start_idx)

        # Collect the response content piece by piece
        for piece in get_response(model, messages, temperature, top_p):
            logging.error(f"Received piece: {piece}")
            response_content += piece

            # Append the piece to the buffer
            def update_buffer_with_piece(p=piece):
                buffer_content = conv_buf[:response_start_idx]
                buffer_content.extend(response_content.split("\n"))

                conv_buf[:] = buffer_content
                self.nvim.command('normal! G$')
                self.nvim.command('redraw')

            self.nvim.async_call(update_buffer_with_piece)
            time.sleep(0.01)  # Small delay to make the output visible

        def append_end_separator():
            conv_buf[:] = conv_buf[:] + ['---', '', '']
            self.nvim.command('normal! G$')
            self.nvim.command('redraw')
            logging.error("Appended end separator after response.")

        self.nvim.async_call(append_end_separator)

        # Apply LLM-suggested changes
        self.apply_llm_changes(response_content)
        logging.error("fetch_and_display function completed successfully")

    def apply_llm_changes(self, response_content):
        import re

        # Parse response_content for REPLACE blocks
        replace_pattern = re.compile(
            r'^--- REPLACE (\d+) (\d+) WITH ---\n([\s\S]+?)\n--- END ---',
            re.MULTILINE
        )

        # Convert from string to int and to 0-based index
        def parse(x):
            start, end, new_code = x
            return [int(start) - 1, int(end) - 1, new_code]

        # start, end, new_code
        replacements = list(map(parse, replace_pattern.findall(response_content)))
        for i in range(len(replacements)):
            start, end, new_code = replacements[i]
            new_code_lines = new_code.split('\n')

            def apply_change(s=start, e=end, code=new_code_lines):
                try:
                    if self.nvim.api.buf_is_valid(self.code_buffer):
                        self.code_buffer[s:e+1] = code
                        logging.error(f"Applied changes from lines {s+1} to {e+1}")
                    else:
                        logging.error("Code buffer is no longer valid.")
                except Exception as e:
                    logging.error(f"Failed to apply changes: {e}")

            self.nvim.async_call(apply_change)
            time.sleep(0.01)

            # We probably changed the line numbers of all the code above/below,
            # so adjust the line numbers of subsequent changes
            for j in range(i + 1, len(replacements)):
                other_start, other_end, other_new_code = replacements[j]

                # If the other change is before the change we just made, it's fine
                if other_end < start: continue

                # Make sure there are no overlapping changes
                if (other_start >= start and other_start <= end) \
                        or (other_end >= start and other_end <= end):
                    logging.error(f"Change mismatch! {start} - {end} overlaps {other_start} - {other_end}")

                # Adjust
                line_count_mismatch = len(new_code_lines) - (end - start + 1)
                replacements[j][0] += line_count_mismatch
                replacements[j][1] += line_count_mismatch
            
    def parse_buffer_content(self, lines):
        messages = []
        message_content = []
        role = 'user'  # Assume conversation starts with user
        idx = 0
        model = None
        # Check for 'MODEL: <model_name>' at the top
        if lines and lines[0].startswith('MODEL: '):
            model = lines[0][len('MODEL: '):].strip()
            idx = 1  # Skip the model line
            # Skip the empty line after the model line if present
            if idx < len(lines) and lines[idx].strip() == '':
                idx += 1

        while idx < len(lines):
            line = lines[idx]
            if line.strip() == '---':
                # Message separator found
                # Append the current message
                if message_content:
                    content = '\n'.join(message_content).strip()
                    if content:
                        messages.append({'role': role, 'content': content})
                # Switch role
                role = 'assistant' if role == 'user' else 'user'
                message_content = []
                # Skip the empty line after '---' if present
                idx += 1
                if idx < len(lines) and lines[idx].strip() == '':
                    idx += 1
                continue
            else:
                message_content.append(line)
                idx += 1
        # Append the last message
        if message_content:
            content = '\n'.join(message_content).strip()
            if content:
                messages.append({'role': role, 'content': content})
        return model, messages

    @pynvim.command('LLMSelectModel', nargs='*', sync=False)
    def llm_select_model_command(self, args):
        logging.error("llm_select_model_command called")
        self.llm_select_model(args)

    def llm_select_model(self, args):
        # Prepare models for Lua code
        # Use JSON to safely serialize the list
        import json
        models_json = json.dumps(models)

        # Load Lua code from a separate file
        with open(os.path.join(self.lua_dir, 'select_model.lua'), 'r') as f:
            lua_code = f.read()

        self.nvim.async_call(lambda: self.nvim.exec_lua(lua_code, models))

    @pynvim.function('LLMModelSelected', sync=False)
    def llm_model_selected(self, args):
        selected_model = args[0]
        # Insert 'MODEL: selected_model' into the minibuffer
        conv_buf = self.nvim.buffers[self.conversation_buffer]
        # Insert or replace the model line at the top of the buffer
        lines = conv_buf[:]
        model_line = 'MODEL: ' + selected_model
        if lines and lines[0].startswith('MODEL: '):
            conv_buf[0] = model_line
        else:
            conv_buf[0:0] = [model_line, '']
        logging.error(f"Model selected: {selected_model}")
        # Inform the user about the selection
        self.nvim.out_write(f"Model selected: {selected_model}\n")
