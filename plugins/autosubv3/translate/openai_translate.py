import time
import random
from typing import List, Union, Tuple, Optional

import openai
import httpx
from cacheout import Cache

OpenAISessionCache = Cache(maxsize=100, ttl=3600, timer=time.time, default=None)


class OpenAi:
    _api_key: str = None
    _api_url: str = None
    _model: str = "gpt-4o-mini"

    def __init__(self, api_key: str = None, api_url: str = None, proxy: dict = None, model: str = None,
                 compatible: bool = False):
        self._api_key = api_key
        self._api_url = api_url
        base_url = self._api_url if compatible else self._api_url + "/v1"

        # 创建 OpenAI 客户端实例
        if proxy and proxy.get("https"):
            http_client = httpx.Client(proxies=proxy.get("https"))
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url, http_client=http_client)
        else:
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url)

        if model:
            self._model = model

    @staticmethod
    def __save_session(session_id: str, message: str):
        """
        保存会话
        :param session_id: 会话ID
        :param message: 消息
        :return:
        """
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({
                "role": "assistant",
                "content": message
            })
            OpenAISessionCache.set(session_id, seasion)

    @staticmethod
    def __get_session(session_id: str, message: str) -> List[dict]:
        """
        获取会话
        :param session_id: 会话ID
        :return: 会话上下文
        """
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({
                "role": "user",
                "content": message
            })
        else:
            seasion = [
                {
                    "role": "system",
                    "content": "请在接下来的对话中请使用中文回复，并且内容尽可能详细。"
                },
                {
                    "role": "user",
                    "content": message
                }]
            OpenAISessionCache.set(session_id, seasion)
        return seasion

    def __get_model(self, message: Union[str, List[dict]],
                    prompt: str = None,
                    **kwargs):
        """
        获取模型
        """
        if not isinstance(message, list):
            if prompt:
                message = [
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            else:
                message = [
                    {
                        "role": "user",
                        "content": message
                    }
                ]
        return self.client.chat.completions.create(
            model=self._model,
            messages=message,
            **kwargs
        )

    @staticmethod
    def __clear_session(session_id: str):
        """
        清除会话
        :param session_id: 会话ID
        :return:
        """
        if OpenAISessionCache.get(session_id):
            OpenAISessionCache.delete(session_id)

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = 3):
        """
        翻译为中文（单条）
        :param text: 输入文本
        :param context: 翻译上下文
        :param max_retries: 最大重试次数
        """
        system_prompt = "你是字幕翻译专家。只输出译文，保持行号："
        user_prompt = f"翻译为中文：\n{text}"

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(prompt=system_prompt,
                                              message=user_prompt,
                                              temperature=0.2,
                                              top_p=0.9)
                result = completion.choices[0].message.content.strip()
                return True, result
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    # 使用指数退避和随机抖动，避免多个请求同时重试
                    base_delay = 2 ** attempt  # 指数退避: 1s, 2s, 4s...
                    jitter = random.uniform(0.1, 0.9)  # 随机抖动: 0.1-0.9秒
                    sleep_time = base_delay + jitter
                    print(f"翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, f"{last_error}"

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3) -> Tuple[bool, List[Optional[str]]]:
        """
        批量翻译为中文（带行号）
        :param texts: 输入文本列表
        :param max_retries: 最大重试次数
        :return: (成功标志, 翻译结果列表)
        """
        system_prompt = "你是字幕翻译专家。只输出译文，保持行号："
        
        # 构建带行号的输入
        input_lines = [f"{i+1}. {text}" for i, text in enumerate(texts)]
        user_prompt = "\n".join(input_lines)
        
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    prompt=system_prompt,
                    message=user_prompt,
                    temperature=0.2,
                    top_p=0.9
                )
                result = completion.choices[0].message.content.strip()
                
                # 解析带行号的输出
                translations = [None] * len(texts)
                lines = result.split('\n')
                
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 0:
                        # 解析 "1. 翻译内容" 格式
                        if line[0].isdigit() and '. ' in line[:5]:
                            try:
                                num_part, content = line.split('.', 1)
                                num = int(num_part.strip())
                                if 1 <= num <= len(texts):
                                    translations[num - 1] = content.strip()
                            except (ValueError, IndexError):
                                pass
                
                # 检查是否有未翻译的条目
                failed_count = sum(1 for t in translations if t is None)
                if failed_count > 0:
                    print(f"批量翻译部分失败：{failed_count}/{len(texts)} 条未匹配，将降级处理")
                    return False, translations
                
                return True, translations
                
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    base_delay = 2 ** attempt
                    jitter = random.uniform(0.1, 0.9)
                    sleep_time = base_delay + jitter
                    print(f"批量翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"批量翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, [None] * len(texts)
