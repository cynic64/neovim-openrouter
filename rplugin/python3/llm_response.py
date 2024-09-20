import pynvim
from core import get_response
import time
import logging
import threading

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
        self.query_buffers = {}  # Keep track of query buffers
        self.selected_text = None  # Store selected text if any

    @pynvim.function("LLMResponse", sync=False)
    def llm_response(self, args):
        logging.error("llm_response function called")

        # Get the selection from register 's'
        self.selected_text = self.nvim.funcs.getreg('s')
        if self.selected_text == '':
            self.selected_text = None
            logging.error("No visual selection detected")
        else:
            self.selected_text = f"```\n{self.selected_text}\n```"
            logging.error(f"Selected text: {self.selected_text}")

        # Create a new scratch buffer
        buf = self.nvim.api.create_buf(False, True)

        # Set buffer options
        self.nvim.api.buf_set_option(buf, 'buftype', 'nofile')
        self.nvim.api.buf_set_option(buf, 'swapfile', False)
        self.nvim.api.buf_set_option(buf, 'bufhidden', 'wipe')

        # Open a new window for the buffer at the bottom
        height = 10  # Adjust the height as needed
        self.nvim.command(f"botright {height}split")
        self.nvim.command(f"buffer {buf.number}")

        # If there is selected text, populate the buffer with it
        if self.selected_text:
            initial_content = self.selected_text.split('\n') + ['']
            buf[:] = initial_content
            # Move the cursor to the end of the buffer
            self.nvim.current.window.cursor = (len(initial_content), 0)
        else:
            # Ensure the buffer is empty
            buf[:] = ['']
            # Cursor at the first line
            self.nvim.current.window.cursor = (1, 0)

        # Set up a buffer-local key mapping to trigger submission
        # Map <F5> to call the function LLMSubmitCommand
        self.nvim.api.buf_set_keymap(
            buf.number,
            'n',
            '<F5>',
            ':LLMSubmitCommand<CR>',
            {'nowait': True, 'noremap': True, 'silent': True}
        )
        self.nvim.api.buf_set_keymap(
            buf.number,
            'i',
            '<F5>',
            '<Esc>:LLMSubmitCommand<CR>',
            {'nowait': True, 'noremap': True, 'silent': True}
        )

        # Store the buffer number to identify it later
        self.query_buffers[buf.number] = buf

        logging.error(f"Opened buffer {buf.number} for input")

    @pynvim.command('LLMSubmitCommand', nargs='*', sync=False)
    def llm_submit_command(self, args):
        logging.error("llm_submit_command called")
        self.llm_submit(args)

    def llm_submit(self, args):
        logging.error("llm_submit function called")

        # Get the current buffer (should be the minibuffer)
        buf = self.nvim.current.buffer

        # Get the text from the buffer
        full_query = "\n".join(buf[:])

        logging.error(f"Full query from buffer: {full_query}")

        # Split the buffer content into lines
        lines = buf[:]

        # Prepare the content to display in the buffer
        # We'll separate the query and response with a separator
        def fetch_and_display():
            response_content = ''  # Accumulate the response pieces here

            for piece in get_response(full_query):
                logging.error(f"Received piece: {piece}")

                response_content += piece

                # Since we're in a different thread, schedule buffer updates in the main thread
                def update_buffer():
                    # Build the buffer content to include the separator and response
                    buffer_content = lines + ['---', ''] + response_content.split('\n')

                    # Replace the entire buffer content
                    buf[:] = buffer_content

                    # Move the cursor to the end
                    self.nvim.command(f"normal! G$")
                    self.nvim.command('redraw')

                    logging.error(f"Updated buffer with response content")

                self.nvim.async_call(update_buffer)
                # Small delay to make the output visible
                time.sleep(0.01)

            logging.error("llm_submit function completed successfully")

        # Start a new thread to fetch and display the response
        threading.Thread(target=fetch_and_display).start()
