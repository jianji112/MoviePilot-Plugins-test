import time
import random
import re
import json
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

        if proxy and proxy.get("https"):
            http_client = httpx.Client(proxies=proxy.get("https"))
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url, http_client=http_client)
        else:
            self.client = openai.OpenAI(api_key=self._api_key, base_url=base_url)

        if model:
            self._model = model

    @staticmethod
    def __save_session(session_id: str, message: str):
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({"role": "assistant", "content": message})
            OpenAISessionCache.set(session_id, seasion)

    @staticmethod
    def __get_session(session_id: str, message: str) -> List[dict]:
        seasion = OpenAISessionCache.get(session_id)
        if seasion:
            seasion.append({"role": "user", "content": message})
        else:
            seasion = [
                {"role": "system", "content": "请在接下来的对话中请使用中文回复，并且内容尽可能详细。"},
                {"role": "user", "content": message}
            ]
            OpenAISessionCache.set(session_id, seasion)
        return seasion

    def __get_model(self, message: Union[str, List[dict]], system_hint: str = None, **kwargs):
        if not isinstance(message, list):
            if system_hint:
                message = [
                    {"role": "system", "content": system_hint},
                    {"role": "user", "content": message}
                ]
            else:
                message = [{"role": "user", "content": message}]
        return self.client.chat.completions.create(model=self._model, messages=message, **kwargs)

    @staticmethod
    def __clear_session(session_id: str):
        if OpenAISessionCache.get(session_id):
            OpenAISessionCache.delete(session_id)

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text or ""
        text = re.sub(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', '', text)
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\s*\n', '', text)
        text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', text)
        text = re.sub(r'([\u4e00-\u9fff])\s+([a-zA-Z0-9])', r'\1\2', text)
        text = re.sub(r'([a-zA-Z0-9])\s+([\u4e00-\u9fff])', r'\1\2', text)
        text = re.sub(r'\s+\n', '\n', text)
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)

    @staticmethod
    def _clean_ai_response(text: str) -> str:
        text = (text or "").strip()
        text = text.replace("```json", "").replace("```", "").strip()
        match = re.search(r'(\[.*\])', text, flags=re.S)
        if match:
            return match.group(1).strip()
        return text

    @staticmethod
    def _validate_batch(input_batch: List[dict], output_batch: List[dict]) -> bool:
        if len(input_batch) != len(output_batch):
            return False
        ids1 = [x["id"] for x in input_batch]
        ids2 = [x.get("id") for x in output_batch]
        if ids1 != ids2:
            return False
        for item in output_batch:
            zh = item.get("zh")
            if not isinstance(zh, str) or not zh.strip():
                return False
        return True

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = 3):
        """单条翻译：走 3.5.10 prompt 思路"""
        text = self._clean_text(text)
        context = self._clean_text(context) if context else None

        system_prompt = """您是一位专业字幕翻译专家，请严格遵循以下规则：
1. 将原文精准翻译为简体中文，保持原文本意
2. 使用自然的口语化表达，符合中文观影习惯
3. 结合上下文语境，人物称谓、专业术语、情感语气在上下文中保持连贯
4. 按行翻译待译内容。翻译结果不要包括上下文。
5. 输出内容必须仅包括译文。不要输出任何开场白，解释说明或总结
6. 遇到英文脏话时请翻译成自然中文口语，不要保留英文单词"""
        user_prompt = f"翻译上下文：\n{context}\n\n需要翻译的内容：\n{text}" if context else f"请翻译：\n{text}"

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=user_prompt,
                    system_hint=system_prompt,
                    temperature=0.2,
                    top_p=0.9
                )
                result = completion.choices[0].message.content.strip()
                result = self._clean_text(result)
                return True, result
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 0.9)
                    print(f"翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, f"{last_error}"

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3) -> Tuple[bool, List[Optional[str]]]:
        """批量翻译：JSON结构化输出，按id校验，尽量避免串行"""
        input_batch = []
        for idx, text in enumerate(texts, 1):
            input_batch.append({
                "id": idx,
                "text": self._clean_text(text)
            })

        prompt = f"""
你是专业字幕翻译器。

规则：
1. 不得改变 id
2. 不得合并字幕
3. 不得新增字幕
4. 只翻译 text
5. 输出 JSON 数组
6. 输出数量必须与输入一致
7. 每个 id 只翻译自己的 text，不要借用前后字幕的内容
8. 要尽量口语化，符合上下文语境
9. 遇到英文脏话时请翻成自然中文口语，不要保留英文脏字

输入：
{json.dumps(input_batch, ensure_ascii=False)}

输出示例：
[
  {{"id":1,"zh":"你好世界"}}
]
""".strip()

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=prompt,
                    temperature=0,
                    top_p=1
                )
                raw_text = completion.choices[0].message.content.strip()
                clean_text = self._clean_ai_response(raw_text)
                output_batch = json.loads(clean_text)

                if not isinstance(output_batch, list):
                    raise ValueError("AI输出不是JSON数组")
                if not self._validate_batch(input_batch, output_batch):
                    raise ValueError("AI输出数量或id不匹配")

                translations: List[Optional[str]] = [None] * len(texts)
                for item in output_batch:
                    idx = int(item["id"]) - 1
                    zh = self._clean_text(item["zh"])
                    if 0 <= idx < len(translations):
                        translations[idx] = zh
                return True, translations
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    sleep_time = (2 ** attempt) + random.uniform(0.1, 0.9)
                    print(f"批量翻译请求失败 (第{attempt + 1}次尝试)：{last_error}，{sleep_time:.1f}秒后重试...")
                    time.sleep(sleep_time)
                else:
                    print(f"批量翻译请求失败 (已重试{max_retries}次)：{last_error}")
                    return False, [None] * len(texts)
