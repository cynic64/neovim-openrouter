import requests
import json
import logging

with open("/home/void/.config/nvim/rplugin/python3/api_key") as f:
    OPENROUTER_API_KEY = f.read().rstrip()

def get_response(query: str):
    logging.error(f"get_response for query {query}")

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        },
        data=json.dumps({
            "model": "google/gemini-pro-1.5-exp",
            "stream": True,
            "messages": [
                {"role": "user", "content": query}
            ]
        }),
        stream=True  # This is important for streaming the response
    )

    text = []

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
                if 'choices' in data and len(data['choices']) > 0:
                    delta = data['choices'][0].get('delta', {})
                    if 'content' in delta:
                        yield delta['content']
            except json.JSONDecodeError:
                pass

if __name__ == "__main__":
    import sys

    for piece in get_response(sys.stdin.read().rstrip()):
        print(piece, end="", flush=True)

    print()
