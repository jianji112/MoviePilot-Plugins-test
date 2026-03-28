import time
import random
import re
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
                    system_hint: str = None,
                    **kwargs):
        """
        获取模型
        """
        if not isinstance(message, list):
            if system_hint:
                message = [
                    {
                        "role": "system",
                        "content": system_hint
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
        # 清理输入：去除多余空格、修复被空格分开的汉字
        text = self._clean_text(text)
        
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=text,
                    system_hint="你是字幕翻译专家。直接输出翻译结果，不要任何前缀、不要保持行号、不要保留原文，只输出翻译后的中文字幕内容。",
                    temperature=0.2,
                    top_p=0.9
                )
                result = completion.choices[0].message.content.strip()
                # 清理输出：去除可能的原文残留
                result = self._clean_text(result)
                return True, result
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    base_delay = 2 ** attempt
                    jitter = random.uniform(0.1, 0.9)
                    sleep_time = base_delay + jitter
                    print(f"翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, f"{last_error}"

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        清理字幕文本：
        1. 去除多余空格（汉字之间的空格、句首句尾空格）
        2. 去除时间轴残留（如 00:00:00,000 --> 00:00:05,360）
        3. 去除行号残留（如单独的 1、2、3 在一行）
        4. 去除SRT块号残留
        """
        import re
        # 去除时间轴行
        text = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', '', text)
        # 去除单独的纯数字行（行号残留）
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        # 去除块号（如 "1" 在行首后换行）
        text = re.sub(r'^\s*\d+\s*\n', '', text)
        # 汉字之间多余空格
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
        # 字母/数字与汉字之间多余空格
        text = re.sub(r'([\u4e00-\u9fff])\s+([a-zA-Z0-9])', r'\1\2', text)
        text = re.sub(r'([a-zA-Z0-9])\s+([\u4e00-\u9fff])', r'\1\2', text)
        # 句尾多余空格
        text = re.sub(r'\s+\n', '\n', text)
        # 去除每行首尾多余空格
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
        return text

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3) -> Tuple[bool, List[Optional[str]]]:
        """
        批量翻译为中文（带行号）
        :param texts: 输入文本列表
        :param max_retries: 最大重试次数
        :return: (成功标志, 翻译结果列表)
        """
        # 清理每条输入文本
        cleaned_texts = [self._clean_text(text) for text in texts]
        
        # 构建输入：直接用换行分隔，不要带数字前缀
        user_prompt = "\n".join(cleaned_texts)
        
        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=user_prompt,
                    system_hint="你是字幕翻译专家。直接翻译以下字幕，每行对应一条字幕的翻译结果，不要加行号前缀，不要加任何序号，只输出翻译后的纯文本，每行对应一条翻译。",
                    temperature=0.2,
                    top_p=0.9
                )
                result = completion.choices[0].message.content.strip()
                
                # 解析输出：每行对应一条翻译
                translated_lines = result.split('\n')
                translations = []
                for line in translated_lines:
                    line = line.strip()
                    # 去除可能的行号前缀如 "1. " 或 "1 "
                    line = re.sub(r'^[\d]+\.\s*', '', line)
                    translations.append(line)
                
                # 如果返回行数不匹配，截断或填充
                if len(translations) > len(texts):
                    translations = translations[:len(texts)]
                elif len(translations) < len(texts):
                    translations.extend([None] * (len(texts) - len(translations)))
                
                # 检查是否有未翻译的条目
                failed_count = sum(1 for t in translations if t is None or not t.strip())
                if failed_count > 0:
                    print(f"批量翻译部分失败：{failed_count}/{len(texts)} 条为空，将降级处理")
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
