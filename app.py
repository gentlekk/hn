import sqlite3
from flask import Flask, render_template, request,jsonify
import requests
import re
import markdown
from routes.hidream_client import HiDreamClient
from routes import spark_agent


app = Flask(__name__)
# 主页面 index.html
@app.route('/')
def index():
    return render_template('index.html')

# 展馆页面 exhibit.html
@app.route('/exhibit/<int:hall_id>')
def show_exhibit(hall_id):
    conn = sqlite3.connect('artifacts.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, description FROM halls WHERE id = ?", (hall_id,))
    hall = cursor.fetchone()
    if hall:
        hall_name, hall_desc = hall
    else:
        hall_name, hall_desc = ""
    cursor.execute("SELECT name, description, image_path FROM artifacts WHERE hall_id = ?", (hall_id,))
    artifacts = cursor.fetchall()
    conn.close()
    return render_template('exhibit.html', hall_id=hall_id, hall_name=hall_name,hall_desc=hall_desc ,artifacts=artifacts)



# 文物讲解 explain.html 
SPARK_API_KEY = "hOsAqvPOPxkYNntIFelc:fSQoYvXRZLEDIoiKJrrj"
SPARK_BASE_URL = "https://spark-api-open.xf-yun.com/v2"
SPARK_API_PATH = "/chat/completions"
SPARK_MODEL = "x1"

def call_spark_model(artifact_name, user_id="user_123456"):
    url = SPARK_BASE_URL + SPARK_API_PATH
    headers = {
        "Authorization": f"Bearer {SPARK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": SPARK_MODEL,
        "user": user_id,
        "messages": [
            {"role": "system", "content": "你是河南博物院的文物讲解员"},
            {"role": "user", "content": f"请介绍文物《{artifact_name}》，包括其历史背景、文化价值与艺术特色。"}
        ],
        "stream": False
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        print("状态码:", response.status_code)
        print("响应内容:", response.text)

        result = response.json()
        if result.get("code") == 0 and "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            return f"模型响应错误：{result.get('message', '无详细错误信息')}"
    except requests.exceptions.ProxyError as e:
        return f"调用模型出错：代理连接失败，请检查代理设置。详细：{str(e)}"
    except requests.exceptions.SSLError as e:
        return f"调用模型出错:SSL验证失败,请检查网络或证书。详细：{str(e)}"
    except Exception as e:
        return f"调用模型出错：{str(e)}"

# 模型调用文物讲解页面
@app.route('/explain', methods=['GET', 'POST'])
def explain():
    explanation = None
    if request.method == 'POST':
        artifact_name = request.form.get('artifact_name', '')
        explanation = call_spark_model(artifact_name)
        # 将HTML标签转换为Markdown
        explanation=markdown.markdown(explanation)
        # 删除HTML标签
        explanation=re.sub(r'<[^>]+>', '', explanation)
    return render_template('explain.html', explanation=explanation)


# 图片生成 hidream.html hidream_client.py output_images
# HiDream配置
HIDREAM_APP_ID = "b5efc52c"
HIDREAM_API_SECRET = "Zjg5ZTcyMjNjY2M1M2IwMzIxMDEwOWIy"
HIDREAM_API_KEY = "a598b1cf8533c083ec38aceea0ced764"
HIDREAM_CREATE_URL = "https://cn-huadong-1.xf-yun.com/v1/private/s3fd61810/create"
HIDREAM_QUERY_URL = "https://cn-huadong-1.xf-yun.com/v1/private/s3fd61810/query"

# 初始化HiDream客户端
hidream_client = HiDreamClient(HIDREAM_APP_ID, HIDREAM_API_SECRET, HIDREAM_API_KEY, HIDREAM_CREATE_URL, HIDREAM_QUERY_URL)

# HiDream图片生成页面
@app.route('/hidream', methods=['GET', 'POST'])
def hidream():
    if request.method == 'POST':
        prompt = request.form.get('prompt', '').strip()
        filename = request.form.get('filename', '').strip()
        
        if not prompt:
            return render_template('hidream.html', error="提示词不能为空！")
        
        try:
            # 生成图片
            saved_path = hidream_client.generate_and_save_image(prompt, filename if filename else None)
            
            # 获取相对路径用于前端显示
            relative_path = saved_path.replace('static\\', '').replace('static/', '').replace('\\', '/')
            
            return render_template('hidream.html', 
                                 success=True, 
                                 image_path=relative_path, 
                                 prompt=prompt)
        except Exception as e:
            return render_template('hidream.html', error=f"生成失败: {str(e)}")
    
    return render_template('hidream.html')



# 智能体 ai_agent.html  spark_agent.py

def call_spark_agent_api(prompt):
    # 这里是示例，替换成你的请求代码和鉴权
    url = "https://xingchen-api.xf-yun.com/workflow/v1/chat/completion"
    headers = {
        "Content-Type": "application/json",
        "X-Appid": "你的AppID",
        "X-Api-Key": "你的APIKey",
        # 其他鉴权头部...
    }
    data = {
        "prompt": prompt,
        # 其他请求参数
    }
    # 注意根据接口要求调整请求格式，以下示例为POST
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()

@app.route("/ai_agent", methods=["GET", "POST"])
def ai_agent():
    if request.method == "GET":
        return render_template("ai_agent.html")
    # POST 请求
    user_input = request.form.get("user_input", "")
    if not user_input.strip():
        return jsonify({"error": "输入不能为空"})
    result = spark_agent.send_message(user_input)
    return jsonify(result)





if __name__ == '__main__':
    app.run(debug=True)