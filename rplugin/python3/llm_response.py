import pynvim
from core import get_response
import time
import logging
import threading
import os
import re

SYSTEM_PROMPT = """If you suggest changes to code you were given, always use the following format:
--- REPLACE ---
lines of old code you want to replace
can be multiple lines
--- WITH ---
new code you want to replace it with
can also be multiple lines
--- END ---

note that the "old code" section has to be unique within the code you were
given. If there are multiple locations in the code that match the "old code"
you gave, an error will be thrown.
"""

# model name -> (temperature, top_p)
parameters = {
    "anthropic/claude-3.5-sonnet:beta": (0.9, 0.9),
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
            self.selected_text = f"```\n{self.selected_text}\n```"
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

    def find_multiline(self, buffer, text_lines):
        """
        Search for a sequence of lines in the buffer that exactly matches text_lines.
        Returns a tuple (start_index, end_index) if found, else None.
        """
        for i in range(len(buffer) - len(text_lines) + 1):
            if buffer[i:i + len(text_lines)] == text_lines:
                return (i, i + len(text_lines))
        return None

    def count_multiline_matches(self, buffer, text_lines):
        """
        Counts how many times a sequence of lines appears in the buffer.
        """
        count = 0
        for i in range(len(buffer) - len(text_lines) + 1):
            potential_match = buffer[i:i + len(text_lines)]
            if potential_match == text_lines:
                count += 1
                logging.error(f"|||{potential_match}||| matches |||{text_lines}||| ({i=})")

        return count

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

        # After collecting the full response, process diffs
        logging.error("Completed fetching full response. Processing diffs if any.")

        # Define the diff pattern
        diff_pattern = r"--- REPLACE ---\n(.*?)\n--- WITH ---\n(.*?)\n--- END ---"
        diffs = re.findall(diff_pattern, response_content, re.DOTALL)

        if diffs:
            logging.error(f"Found {len(diffs)} diff(s) in the response.")
            for old_code, new_code in diffs:
                # Clean and split the code blocks into lines
                old_lines = [line.rstrip() for line in old_code.strip().split('\n')]
                new_lines = [line.rstrip() for line in new_code.strip().split('\n')]

                logging.error(f"Processing diff:\nOld Code:\n{old_code}\nNew Code:\n{new_code}")

                # Fetch the latest buffer content for the code buffer
                buffer_content = None
                def get_code_buffer_content():
                    nonlocal buffer_content
                    buffer_content = code_buf[:]

                self.nvim.async_call(get_code_buffer_content)
                time.sleep(0.01)

                logging.error(f"{buffer_content=}")

                # Find the start and end indices of the old code in the code buffer
                match = self.find_multiline(buffer_content, old_lines)

                if match is None:
                    error_msg = f"Error: No match found for the old lines: |||{old_lines}|||"
                    logging.error(error_msg)
                    self.nvim.async_call(lambda: self.nvim.err_write(error_msg + "\n"))
                    continue

                # Ensure only one occurrence exists
                match_count = self.count_multiline_matches(buffer_content, old_lines)
                if match_count > 1:
                    error_msg = f"Error: Multiple matches ({match_count}) found for the old lines: |||{old_lines}|||"
                    logging.error(error_msg)
                    self.nvim.async_call(lambda: self.nvim.err_write(error_msg + "\n"))
                    continue

                start, end = match
                logging.error(f"Replacing lines {start +1} to {end} with new code.")

                # Define the replacement function
                def perform_replace(start_idx=start, end_idx=end, replacement=new_lines):
                    try:
                        code_buf[start_idx:end_idx] = replacement
                        self.nvim.command('redraw')
                        logging.error(f"Successfully replaced lines {start_idx+1} to {end_idx}.")
                    except Exception as e:
                        logging.error(f"Failed to replace lines: {e}")
                        self.nvim.async_call(lambda: self.nvim.err_write(f"Failed to replace lines: {e}\n"))

                # Schedule the replacement on the main thread
                self.nvim.async_call(perform_replace)

            # Optionally, remove diffs from the response_content before displaying
            response_content = re.sub(diff_pattern, '', response_content, flags=re.DOTALL)

        # Append end separator after processing diffs
        def append_end_separator():
            conv_buf[:] = conv_buf[:] + ['---', '', '']
            self.nvim.command('normal! G$')
            self.nvim.command('redraw')
            logging.error("Appended end separator after response.")

        self.nvim.async_call(append_end_separator)

        logging.error("fetch_and_display function completed successfully")

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
