import pynvim
from core import get_response
import time
import logging
import threading
import os

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
        self.lua_dir = os.path.dirname(os.path.abspath(__file__))

    @pynvim.function("LLMResponse", sync=False)
    def llm_response(self, args):
        logging.error("llm_response function called")

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
            if lines[0] == "":
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
        buf = self.nvim.buffers[self.conversation_buffer]

        # Get the text from the buffer
        lines = buf[:]

        logging.error(f"Full conversation from buffer: {lines}")

        # Parse the buffer content into model and messages
        model, messages = self.parse_buffer_content(lines)

        logging.error(f"Parsed model: {model}")
        logging.error(f"Parsed messages: {messages}")

        # Start a new thread to fetch and display the response
        threading.Thread(target=self.fetch_and_display, args=(buf, model, messages)).start()

    def fetch_and_display(self, buf, model, messages):
        logging.error("fetch_and_display function started")
        response_content = ''

        # Append separator and empty line in the main thread
        def append_separator():
            buf[:] = buf[:] + ['---', '']
            self.nvim.command(f"normal! G$")
            self.nvim.command('redraw')

        # Get the index where the response starts
        response_start_idx = None

        def get_response_start_idx():
            nonlocal response_start_idx
            response_start_idx = len(buf[:])

        # Append separator and get response start index
        self.nvim.async_call(append_separator)
        time.sleep(0.01)  # Wait to ensure separator is appended
        self.nvim.async_call(get_response_start_idx)
        time.sleep(0.01)  # Wait to ensure index is retrieved

        for piece in get_response(model, messages):
            logging.error(f"Received piece: {piece}")

            # Append the piece to the response_content
            response_content += piece

            # Since we're in a different thread, schedule buffer updates in the main thread
            def update_buffer():
                # Update the buffer from response_start_idx onwards
                buffer_content = buf[:response_start_idx]
                # Append response_content, splitting it into lines
                buffer_content.extend(response_content.split('\n'))
                buf[:] = buffer_content
                # Move the cursor to the end
                self.nvim.command(f"normal! G$")
                self.nvim.command('redraw')

                logging.error(f"Updated buffer with response content")

            self.nvim.async_call(update_buffer)
            # Small delay to make the output visible
            time.sleep(0.01)

        # After the response is complete, append '---\n\n' so you can start typing
        def append_end_separator():
            buf[:] = buf[:] + ['---', '', '']
            self.nvim.command(f"normal! G$")
            self.nvim.command('redraw')

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
        models = [
            "anthropic/claude-3.5-sonnet",
            "openai/o1-mini",
            "google/gemini-pro-1.5-exp",
            "openai/o1-preview",
            # Add more models as needed
        ]

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
        buf = self.nvim.buffers[self.conversation_buffer]
        # Insert or replace the model line at the top of the buffer
        lines = buf[:]
        model_line = 'MODEL: ' + selected_model
        if lines and lines[0].startswith('MODEL: '):
            buf[0] = model_line
        else:
            buf[0:0] = [model_line, '']
        logging.error(f"Model selected: {selected_model}")
        # Inform the user about the selection
        self.nvim.out_write(f"Model selected: {selected_model}\n")
