import base64
import json
import urllib.request
import urllib.error

DEEPSEEK_BASE = 'https://api.deepseek.com'
CHAT_ENDPOINT = f'{DEEPSEEK_BASE}/chat/completions'


def _call_api(api_key: str, messages: list[dict], model: str = 'deepseek-chat',
              max_tokens: int = 4096, temperature: float = 0.1,
              json_mode: bool = True) -> str:
    payload_dict = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': temperature,
    }
    if json_mode:
        payload_dict['response_format'] = {'type': 'json_object'}
    payload = json.dumps(payload_dict).encode('utf-8')

    req = urllib.request.Request(CHAT_ENDPOINT, data=payload, method='POST')
    req.add_header('Authorization', f'Bearer {api_key}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        raise RuntimeError(f'DeepSeek API 错误 ({e.code}): {body}') from e


def extract_from_image(image_path: str, prompt: str, api_key: str) -> str:
    with open(image_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    ext = image_path.rsplit('.', 1)[-1].lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg'}.get(ext, 'image/png')
    data_url = f'data:{mime};base64,{img_b64}'

    messages = [
        {
            'role': 'user',
            'content': [
                {'type': 'image_url', 'image_url': {'url': data_url}},
                {'type': 'text', 'text': prompt},
            ]
        }
    ]
    return _call_api(api_key, messages, model='deepseek-v4-pro', json_mode=False)


def structure_text(text: str, prompt: str, api_key: str) -> str:
    messages = [
        {'role': 'system', 'content': prompt},
        {'role': 'user', 'content': text},
    ]
    return _call_api(api_key, messages, model='deepseek-chat')
