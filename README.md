# AutoSubv3 魔改版 - AI字幕生成插件
基于 MoviePilot autosubv2 插件魔改，支持了最新的OpenAi SDK,修改插件为并行翻译效率翻倍。
目录监控视频文件，用 Whisper AI 识别语音生成字幕，并可选用ai大模型翻译成中文自动生成srt字幕。

## 功能特性
- 支持 OpenAI API 及兼容接口（如硅基流动）
- 入库自动生成str字幕并用AI 翻译为中文
- 支持选择输出双语字幕或者仅中文字幕

## 设置参考(填这两个就行,其他保持默认,没有api的话可以看下面的申请教程)
<img width="1497" height="1768" alt="image" src="https://github.com/user-attachments/assets/1d6cfec0-3191-4547-8822-d30a7dc7c4d6" />

## 申请硅基流动 API
**[也可以用别家的api,只要是支持openai协议的都行]**

### 1. 注册账号

访问 [硅基流动官网](https://cloud.siliconflow.cn/i/QhTuVb78) 注册账号。

### 2. 获取 API Key

1. 登录后进入控制台
2. 先**实名认证**
3. 认证后领取**16元代金券**
  <img width="2064" height="965" alt="image" src="https://github.com/user-attachments/assets/054adb05-4f2a-4466-a85b-585659a7b32d" />

5. 点击「API Keys」菜单
6. 点击「创建 API Key」
7. 复制生成的 Key（格式：`sk-xxx`）
<img width="814" height="867" alt="image" src="https://github.com/user-attachments/assets/57e520ef-9a3e-489c-8146-814d7d91f7ab" />


### 3. 选择翻译模型

推荐使用性价比高的无推理模型,翻译快，如：
- `inclusionAI/Ling-flash-2.0`


## 配置插件

### 1. 安装插件

在 MoviePilot 中添加本仓库地址：
```
https://github.com/jianji112/MoviePilot-Plugins/
```

### 2. 配置参数

在插件设置中填写：

| 参数 | 说明 | 示例 |
|------|------|------|
| API Key | 硅基流动的 API Key | `sk-xxx...` |
| API 地址 | API 端点 | `https://api.siliconflow.cn` |
| 模型 | 翻译模型名称 | `inclusionAI/Ling-flash-2.0` |
| 批量大小 | 每批翻译条数 | `10` |
<img width="1386" height="837" alt="image" src="https://github.com/user-attachments/assets/0189cf07-4c55-4131-8d64-5c551a64b495" />

### 3. 批量大小说明

- 建议设置为 **10**，平衡速度和准确性
- 批量越大速度越快，但匹配率可能下降
- 如果翻译结果出现乱序，可降低批量大小


## 常见问题

### Q: 翻译结果为空或失败？
A: 检查日志或者 API Key 是否正确;

### Q: 如何查看翻译进度？
A: 在 MoviePilot 日志中查看插件输出

## 版本历史

- v3.5.12: 翻译优化，精简提示词+批量翻译，节省80% tokens
- v3.5.11: 修复入库白名单与立即执行冲突
- v3.5.10: 新增路径白名单功能
