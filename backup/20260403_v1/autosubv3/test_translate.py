#!/usr/bin/env python3
"""
autosubv3 翻译模块测试脚本
用法：python3 test_translate.py
"""

import sys
import os
import time
import json

# 添加插件路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translate.openai_translate import OpenAi

# 测试配置 - 使用本地 one-api 服务
API_KEY = os.environ.get("OPENAI_API_KEY", "sk-9ADpMSgZZONG6ZImO1ausUoNbv5WoGLOWPPYyAzIusblPnYv")
API_URL = os.environ.get("OPENAI_API_URL", "http://192.168.86.113:3010")
MODEL = os.environ.get("OPENAI_MODEL", "inclusionAI/Ling-flash-2.0")

# 测试字幕文件
TEST_SRT = "/home/chen/共享/2_代码/测试视频.en.srt"

def load_test_srt(limit=50):
    """加载测试字幕，返回字幕列表"""
    import srt
    
    with open(TEST_SRT, 'r', encoding='utf-8') as f:
        content = f.read()
    
    subs = list(srt.parse(content))
    if limit:
        subs = subs[:limit]
    return subs

def test_single_translate(client, texts, limit=50):
    """测试单条翻译"""
    texts = texts[:limit]
    print(f"\n{'='*60}")
    print(f"[单条翻译测试] 共 {len(texts)} 条")
    print('='*60)
    
    start_time = time.time()
    success_count = 0
    fail_count = 0
    
    for i, text in enumerate(texts, 1):  # 翻译所有条目
        ret, result = client.translate_to_zh(text, max_retries=1)
        if ret:
            success_count += 1
            if i <= 5:  # 只显示前5条
                print(f"[{i}] ✓ {text[:30]}... → {result[:30]}...")
        else:
            fail_count += 1
            print(f"[{i}] ✗ {text[:30]}... → 错误: {result}")
    
    elapsed = time.time() - start_time
    print(f"\n单条翻译完成: {success_count} 成功, {fail_count} 失败, 耗时 {elapsed:.2f}s")
    return success_count, fail_count, elapsed

def test_batch_translate(client, texts, batch_size=20):
    """测试批量翻译"""
    print(f"\n{'='*60}")
    print(f"[批量翻译测试] 共 {len(texts)} 条, batch_size={batch_size}")
    print('='*60)
    
    start_time = time.time()
    success_count = 0
    fail_count = 0
    
    # 分批处理
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        ret, results = client.translate_batch_to_zh(batch, max_retries=2)
        
        if ret:
            success_count += sum(1 for r in results if r is not None)
            fail_count += sum(1 for r in results if r is None)
            print(f"[批次 {i//batch_size + 1}] ✓ 成功 {sum(1 for r in results if r is not None)}/{len(batch)}")
        else:
            fail_count += len(batch)
            print(f"[批次 {i//batch_size + 1}] ✗ 批次失败")
    
    elapsed = time.time() - start_time
    print(f"\n批量翻译完成: {success_count} 成功, {fail_count} 失败, 耗时 {elapsed:.2f}s")
    return success_count, fail_count, elapsed

def main():
    if not API_KEY:
        print("❌ 错误: 未设置 OPENAI_API_KEY 环境变量")
        print("用法: OPENAI_API_KEY=sk-xxx python3 test_translate.py")
        sys.exit(1)
    
    print(f"API URL: {API_URL}")
    print(f"Model: {MODEL}")
    print(f"测试文件: {TEST_SRT}")
    
    # 初始化客户端
    client = OpenAi(
        api_key=API_KEY,
        api_url=API_URL,
        model=MODEL,
        compatible=False
    )
    
    # 加载测试字幕
    subs = load_test_srt(limit=50)
    texts = [sub.content for sub in subs]
    print(f"\n加载了 {len(texts)} 条测试字幕")
    
    # 测试单条翻译（翻译所有字幕）
    s_success, s_fail, s_time = test_single_translate(client, texts, limit=50)
    
    # 测试批量翻译
    b_success, b_fail, b_time = test_batch_translate(client, texts, batch_size=20)
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print('='*60)
    print(f"单条翻译: {s_success} 成功, {s_fail} 失败, 耗时 {s_time:.2f}s")
    print(f"批量翻译: {b_success} 成功, {b_fail} 失败, 耗时 {b_time:.2f}s")
    
    if b_time > 0 and s_time > 0:
        speedup = s_time / b_time
        print(f"批量翻译加速比: {speedup:.2f}x")

if __name__ == "__main__":
    main()
