import requests
import json
import logging
from pathlib import Path 

home_dir = Path.home()
with open(f"{home_dir}/.config/nvim/rplugin/python3/api_key") as f:
    OPENROUTER_API_KEY = f.read().rstrip()

def get_response(model, messages):
    logging.error(f"get_response for model {model}, messages {messages}")

    if not model:
        model = 'google/gemini-pro-1.5-exp'  # Default model

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        },
        data=json.dumps({
            "model": model,
            "stream": True,
            "messages": messages
        }),
        stream=True
    )

    for line in response.iter_lines():
        logging.error(f"line: {line}")
        if line:
            # Remove the "data: " prefix
            line = line.decode('utf-8').removeprefix('data: ')
            
            # Skip any non-JSON lines
            if not line.startswith('{'):
                continue
            
            # Parse the JSON
            try:
                data = json.loads(line)
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    if 'content' in delta:
                        yield delta['content']
                # Check for finish reason
                if data.get('choices', [{}])[0].get('finish_reason'):
                    break
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    import sys

    # Example usage with a list of messages
    model = 'google/gemini-pro-1.5-exp'
    messages = [
        {"role": "user", "content": "Hello, who are you?"},
        {"role": "assistant", "content": "I am an AI developed by OpenAI."}
    ]

    for piece in get_response(model, messages):
        print(piece, end="", flush=True)

    print()
