import re
import requests

API_KEY = "a598b1cf8533c083ec38aceea0ced764"
API_SECRET = "Zjg5ZTcyMjNjY2M1M2IwMzIxMDEwOWIy"
FLOW_ID = "7345818009665064962"
BOT_ID = "2974235"
API_URL = "https://xingchen-api.xf-yun.com/workflow/v1/chat/completions"

def build_auth_header(api_key, api_secret):
    token = f"{api_key}:{api_secret}"
    return {"Authorization": f"Bearer {token}"}

headers = build_auth_header(API_KEY, API_SECRET)

# 用于保存会话历史，注意：如果你多用户请改成session等隔离机制
chat_history = []

def extract_text_and_audio(content):
    audio_url = None
    match = re.search(r'<source.*?src="(.*?)"', content)
    if match:
        audio_url = match.group(1)
    # 去除 <audio> 标签和所有HTML标签，保留纯文本
    text_only = re.sub(r'<audio.*?</audio>', '', content, flags=re.S)
    text_only = re.sub(r'<.*?>', '', text_only, flags=re.S).strip()
    return text_only, audio_url

def send_message(user_input):
    global chat_history
    # 把用户输入追加到历史
    chat_history.append({
        "role": "user",
        "content_type": "text",
        "content": user_input
    })

    payload = {
        "flow_id": FLOW_ID,
        "uid": "user_001",
        "parameters": {
            "AGENT_USER_INPUT": user_input
        },
        "ext": {
            "bot_id": BOT_ID,
            "caller": "workflow"
        },
        "stream": False,
        "chat_id": "session_01",
        "history": chat_history
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code != 200:
        return {"error": f"请求失败，状态码：{response.status_code}", "detail": response.text}

    res = response.json()

    # 从接口返回解析回复文本，假设content在这里，具体结构按接口调整
    raw_content = res.get("choices", [{}])[0].get("delta", {}).get("content", "")
    # 把助手回复加到历史
    chat_history.append({
        "role": "assistant",
        "content_type": "text",
        "content": raw_content
    })

    text, audio_url = extract_text_and_audio(raw_content)

    return {
        "text": text,
        "audio": audio_url
    }