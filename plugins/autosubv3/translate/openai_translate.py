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
            seasion.append({
                "role": "assistant",
                "content": message
            })
            OpenAISessionCache.set(session_id, seasion)

    @staticmethod
    def __get_session(session_id: str, message: str) -> List[dict]:
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

    def __get_model(self, message: Union[str, List[dict]], system_hint: str = None, **kwargs):
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
        if OpenAISessionCache.get(session_id):
            OpenAISessionCache.delete(session_id)

    def translate_to_zh(self, text: str, context: str = None, max_retries: int = 3):
        text = self._clean_text(text)

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=text,
                    system_hint="你是字幕翻译专家。直接输出翻译结果，不要任何前缀、不要保持行号、不要保留原文，只输出翻译后的中文字幕内容。",
                    temperature=0.1,
                    top_p=0.3
                )
                result = completion.choices[0].message.content.strip()
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
    def _looks_invalid_batch_result(source_texts: List[str], translations: List[Optional[str]]) -> Tuple[bool, str]:
        if len(translations) != len(source_texts):
            return True, f"数量不匹配: {len(translations)}/{len(source_texts)}"

        missing = sum(1 for t in translations if t is None or not t.strip())
        if missing > 0:
            return True, f"存在空结果: {missing}"

        english_leak = sum(1 for t in translations if re.search(r'[A-Za-z]{3,}', t or ''))
        if english_leak > 0:
            return True, f"存在英文残留: {english_leak}"

        normalized = [re.sub(r'[，。！？、,.!?\s]+', '', (t or '')) for t in translations]
        duplicate_count = sum(1 for i in range(1, len(normalized)) if normalized[i] and normalized[i] == normalized[i - 1])
        if duplicate_count >= 2:
            return True, f"连续重复过多: {duplicate_count}"

        suspicious_shift = 0
        for src, trans in zip(source_texts, translations):
            src = (src or '').strip()
            trans = (trans or '').strip()
            if len(src) <= 12 and len(trans) >= 18:
                suspicious_shift += 1
        if suspicious_shift >= 3:
            return True, f"疑似跨行串义: {suspicious_shift}"

        return False, ""

    def translate_batch_to_zh(self, texts: List[str], max_retries: int = 3) -> Tuple[bool, List[Optional[str]]]:
        cleaned_texts = [self._clean_text(text) for text in texts]
        numbered_lines = [f"[{idx}] {text}" for idx, text in enumerate(cleaned_texts, 1)]
        user_prompt = "\n".join(numbered_lines)

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                completion = self.__get_model(
                    message=user_prompt,
                    system_hint=(
                        "逐条翻译成自然中文字幕。"
                        "严格保留编号，格式 [编号] 译文。"
                        "禁止跨行串义，禁止保留英文，短句单独翻。"
                    ),
                    temperature=0.1,
                    top_p=0.3
                )
                result = completion.choices[0].message.content.strip()

                translations: List[Optional[str]] = [None] * len(texts)
                for line in result.split('\n'):
                    line = line.strip()
                    if not line:
                        continue

                    match = re.match(r'^\[(\d+)\][\s:：.-]*(.*)$', line)
                    if not match:
                        match = re.match(r'^(\d+)[\.、:\-\s]+(.*)$', line)
                    if not match:
                        continue

                    idx = int(match.group(1)) - 1
                    content = self._clean_text(match.group(2))
                    if 0 <= idx < len(translations) and content:
                        translations[idx] = content

                invalid, reason = self._looks_invalid_batch_result(cleaned_texts, translations)
                if invalid:
                    print(f"批量翻译结果疑似串行或异常：{reason}，将降级处理")
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
