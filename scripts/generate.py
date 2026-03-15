import urllib.request
import ssl
import json
import os
import sys
import time
import re
import certifi

API_KEY = os.environ['ANTHROPIC_API_KEY']
MODEL = 'claude-sonnet-4-5-20250929'

def call_claude(prompt, retries=3):
    """Call Anthropic API with web search enabled. Retries on rate limit."""
    body = json.dumps({
        'model': MODEL,
        'max_tokens': 4096,
        'tools': [{'type': 'web_search_20250305', 'name': 'web_search', 'max_uses': 5}],
        'messages': [{'role': 'user', 'content': prompt}]
    }).encode()

    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': API_KEY,
            'Anthropic-Version': '2023-06-01',
        }
    )

    ctx = ssl.create_default_context(cafile=certifi.where())

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                result = json.loads(resp.read())
            text_parts = [b['text'] for b in result['content'] if b['type'] == 'text']
            return '\n'.join(text_parts)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 30 * (attempt + 1)
                print(f'Rate limited. Waiting {wait}s...', file=sys.stderr)
                time.sleep(wait)
            else:
                raise

def extract_email(output):
    """Extract just the SUBJECT/---/body from output, stripping any analysis."""
    # Find the SUBJECT: line and everything after the --- that follows it
    match = re.search(r'(SUBJECT:.+?\n---\n.+)', output, re.DOTALL)
    if match:
        return match.group(1).strip()
    return output

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: generate.py <prompt_file> [context_files...]', file=sys.stderr)
        sys.exit(1)

    prompt_file = sys.argv[1]
    context_files = sys.argv[2:]

    parts = []
    for cf in context_files:
        with open(cf) as f:
            parts.append(f'--- {os.path.basename(cf)} ---\n{f.read()}')

    with open(prompt_file) as f:
        parts.append(f.read())

    prompt = '\n\n'.join(parts)
    raw = call_claude(prompt)

    # Output only the email, not the analysis
    print(extract_email(raw))
