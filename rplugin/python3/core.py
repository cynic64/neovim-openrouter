import requests
import json
import logging

with open("/home/void/.config/nvim/rplugin/python3/api_key") as f:
    OPENROUTER_API_KEY = f.read().rstrip()

DEFAULT_MODEL = "google/gemini-pro-1.5-exp"

def get_response(messages, model=DEFAULT_MODEL):
    logging.error(f"get_response for messages {messages}")

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
        stream=True  # This is important for streaming the response
    )

    for line in response.iter_lines():
        logging.error(f"line: {line}")
        if line:
            # Remove the "data: " prefix
            line = line.decode('utf-8').removeprefix('data: ')
            
            # Skip any non-JSON lines (like the "OPENROUTER PROCESSING" messages)
            if not line.startswith('{'):
                continue
            
            # Parse the JSON
            try:
                data = json.loads(line)
                logging.error(f"data: {data}")
                if "error" in data:
                    yield f"{data['error']}"
                    break

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
    messages = [
        {"role": "user", "content": "Hello, who are you?"},
        {"role": "assistant", "content": "I am an AI developed by OpenAI."}
    ]

    for piece in get_response(messages):
        print(piece, end="", flush=True)

    print()
