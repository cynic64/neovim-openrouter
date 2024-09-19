import pynvim
import time

@pynvim.plugin
class HelloWriter(object):
    def __init__(self, nvim):
        self.nvim = nvim

    @pynvim.function("HelloWrite", sync=False)
    def hello_write(self, args):
        current_line = self.nvim.current.window.cursor[0]
        
        for i in range(1, 11):
            # Generate the text using Python
            text = self.generate_text(i)
            
            # Insert the text below the current line
            self.nvim.command(f'call append({current_line}, "{text}")')
            current_line += 1
            
            # Force Neovim to redraw the screen
            self.nvim.command('redraw')
            
            # Wait for 0.5 seconds
            time.sleep(0.5)

    def generate_text(self, number):
        return f"Hi {number}!"

