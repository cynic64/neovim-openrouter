import pynvim
from core import get_response
import time
import logging

# Set up logging
logging.basicConfig(filename='/tmp/nvim_llm_plugin.log', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

@pynvim.plugin
class LLMResponsePlugin(object):
    def __init__(self, nvim):
        self.nvim = nvim
        logging.error("LLMResponsePlugin initialized")

    @pynvim.function("LLMResponse", sync=False)
    def llm_response(self, args):
        logging.error("llm_response function called")
        buffer = self.nvim.current.buffer

        # Get the start and end positions of the visual selection
        start_row, start_col = self.nvim.eval("getpos(\"'<\")[1:2]")
        end_row, end_col = self.nvim.eval("getpos(\"'>\")[1:2]")
        logging.error(f"Selection: start({start_row}, {start_col}), end({end_row}, {end_col})")

        # Get the selected text
        if start_row == end_row:
            selected_text = buffer[start_row - 1][start_col - 1:end_col]
        else:
            selected_text = "\n".join(
                buffer[start_row - 1 : end_row]
            )
            selected_text = (
                selected_text[:start_col - 1]
                + selected_text[-(len(buffer[end_row - 1]) - end_col + 1) :]
            )
        logging.error(f"Selected text: {selected_text}")

        # Get the response from the LLM piece by piece
        current_row = end_row

        # Insert two newlines after the selected text
        self.nvim.command(f'call append({current_row}, "")')
        self.nvim.command(f'call append({current_row+1}, "")')

        current_row += 1

        for piece in get_response(selected_text):
            logging.error(f"Received piece: {piece}")
            
            # Split the piece into lines
            lines = piece.split('\n')
            
            # Append the first line to the current line
            current_line = buffer[current_row - 1]
            buffer[current_row - 1] = current_line + lines[0]
            
            # Insert any additional lines
            if len(lines) > 1:
                buffer.append(lines[1:], current_row)
                current_row += len(lines) - 1
            
            # Move the cursor to the end of the last inserted line
            self.nvim.command(f"normal! {current_row}G$")
            
            # Force Neovim to update the screen
            self.nvim.command('redraw')
            
            logging.error(f"Appended piece: {piece} ending at row {current_row}")

            # Small delay to make the output visible
            time.sleep(0.01)

        logging.error("llm_response function completed successfully")
