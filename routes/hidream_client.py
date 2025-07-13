import base64
import hashlib
import hmac
import json
import time
import os
from datetime import datetime
from time import mktime
from urllib.parse import urlencode, urlparse
from wsgiref.handlers import format_date_time
from urllib import parse
import requests

class HiDreamClient:
    def __init__(self, app_id, api_secret, api_key, create_url, query_url):
        self.app_id = app_id
        self.api_secret = api_secret
        self.api_key = api_key
        self.create_url = create_url
        self.query_url = query_url

    def create_auth_url(self, url):
        """生成带认证参数的URL"""
        host = urlparse(url).netloc
        path = urlparse(url).path

        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        # 拼接字符串
        signature_origin = "host: " + host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "POST " + path + " HTTP/1.1"

        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(self.api_secret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()

        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')

        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'

        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": host
        }
        # 拼接鉴权参数，生成url
        reUrl = url + '?' + urlencode(v)
        return reUrl

    def get_headers(self, url):
        """获取请求头"""
        headers = {
            'content-type': "application/json",
            'host': urlparse(url).netloc,
            'app_id': self.app_id
        }
        return headers

    def gen_create_request_data(self, text):
        """生成创建任务的请求数据"""
        data = {
            "header": {
                "app_id": self.app_id,
                "status": 3,
                "channel": "default",
                "callback_url": "default",
            },
            "parameter": {
                "oig": {
                    "result": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "json"
                    },
                }
            },
            "payload": {
                "oig": {
                    "text": text
                },
            },
        }
        return data

    def create_task(self, prompt, image_urls=None, aspect_ratio="1:1", img_count=1, resolution="2k"):
        """创建图片生成任务"""
        text = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "negative_prompt": "",
            "img_count": img_count,
            "resolution": resolution
        }
        
        # 如果有图片URL，添加到请求中
        if image_urls:
            text["image"] = image_urls

        # 将text进行base64编码
        b_text = base64.b64encode(json.dumps(text).encode("utf-8")).decode()
        
        # 生成认证URL
        request_url = self.create_auth_url(self.create_url)
        data = self.gen_create_request_data(b_text)
        headers = self.get_headers(self.create_url)
        
        # 发送请求
        response = requests.post(request_url, data=json.dumps(data), headers=headers, timeout=60)
        print('创建任务响应：\n' + response.text)
        
        resp = json.loads(response.text)
        
        # 检查响应格式
        if "header" not in resp:
            error_msg = resp.get("message", "未知错误")
            raise Exception(f"创建任务失败: {error_msg}")
        
        if resp['header']['code'] == 0:
            return resp['header']['task_id']
        else:
            raise Exception(f"创建任务失败: {resp['header']['message']}")

    def query_task(self, task_id, max_retries=30, interval=10):
        """查询任务结果"""
        data = {
            "header": {
                "app_id": self.app_id,
                "task_id": task_id
            }
        }
        
        request_url = self.create_auth_url(self.query_url)
        headers = self.get_headers(self.query_url)

        for _ in range(max_retries):
            response = requests.post(request_url, data=json.dumps(data), headers=headers, timeout=60)
            res = json.loads(response.content)
            print("查询结果:", res)
            
            # 检查响应格式
            if "header" not in res:
                error_msg = res.get("message", "未知错误")
                raise Exception(f"查询失败: {error_msg}")
            
            code = res["header"]["code"]
            if code == 0:
                task_status = res["header"]["task_status"]
                if task_status == '3' or task_status == '4':  # 处理完成或回调完成
                    print("任务完成")
                    f_text = res["payload"]["result"]["text"]
                    # 解析返回的JSON数据
                    decoded_text = base64.b64decode(f_text).decode('utf-8')
                    result_data = json.loads(decoded_text)
                    
                    # 提取图片URL
                    if result_data and len(result_data) > 0:
                        image_url = result_data[0].get('image_wm', '')
                        if image_url:
                            print(f"图片URL: {image_url}")
                            # 下载图片
                            img_response = requests.get(image_url, timeout=60)
                            return img_response.content
                        else:
                            raise Exception("未找到图片URL")
                    else:
                        raise Exception("返回数据格式错误")
                else:
                    print(f"查询任务中：状态 {task_status}，等待 {interval} 秒后重试...")
                    time.sleep(interval)
                    continue
            else:
                raise Exception(f"查询失败: {res['header']['message']}")

        raise TimeoutError("图片生成超时，请稍后重试")

    def generate_and_save_image(self, prompt, filename=None):
        """生成图片并保存到指定目录"""
        # 确保输出目录存在
        output_dir = "static/output_images"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建目录: {output_dir}")
        
        # 如果没有指定文件名，使用时间戳生成文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"generated_{timestamp}.png"
        
        # 确保文件名有.png扩展名
        if not filename.endswith('.png'):
            filename += '.png'
        
        filepath = os.path.join(output_dir, filename)
        
        try:
            print(f"开始生成图片，提示词: {prompt}")
            task_id = self.create_task(prompt)
            print(f"任务创建成功，task_id: {task_id}")
            
            image_bytes = self.query_task(task_id)
            
            # 保存图片
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            
            print(f"图片已保存为: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"生成图片失败: {e}")
            raise e