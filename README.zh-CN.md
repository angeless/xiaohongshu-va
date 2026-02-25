# 视频文案分析工具

[English](README.md) | 中文文档

<div align="center">

**🤖 Claude Skill** | AI 驱动的视频分析工具

[![Claude 4.5 Opus](https://img.shields.io/badge/测试环境-Claude%204.5%20Opus-blue)](https://claude.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

> 🎬 一站式视频内容提取与文案分析工具。下载视频、智能字幕提取（内嵌/烧录/语音）、三维度 AI 框架分析文案。

## ✨ 功能特性

| 阶段 | 功能 | 说明 |
|------|------|------|
| 1️⃣ | **视频下载** | 支持 B站/YouTube/抖音（yt-dlp + 专用下载器） |
| 2️⃣ | **智能字幕提取** | 三层优先级：内嵌字幕 → OCR识别 → 语音转录 |
| 3️⃣ | **智能校正** | 基于上下文自动校正转录错误 |
| 4️⃣ | **三维度分析** | TextContent + Viral + Brainstorming |

## 🚀 快速开始

### 环境要求

```bash
# 1. yt-dlp（视频下载器）
pip install yt-dlp

# 2. FFmpeg（必须安装并添加到 PATH）
ffmpeg -version

# 3. Python 基础依赖
pip install pysrt python-dotenv

# 4. FunASR（中文语音转录，推荐，轻量且效果好）
pip install funasr modelscope

# 5. RapidOCR（ONNX轻量版，用于烧录字幕识别）
pip install rapidocr-onnxruntime

# 6. Whisper（英文/多语言备选方案）
pip install openai-whisper

# 7. requests（抖音下载需要）
pip install requests
```

### 使用方法

这是一个 **Claude Skill**，专为 AI 代理设计。将其安装到 `.agent/skills/` 目录：

```bash
git clone https://github.com/ALBEDO-TABAI/video-copy-analyzer.git .agent/skills/video-copy-analyzer
```

然后与 Claude 对话使用：

> "分析这个视频：https://www.bilibili.com/video/BV1xxxxx"

## 🎯 智能字幕提取（三层优先级）

Skill 会自动选择最佳提取方案：

```
视频输入
    ↓
[1️⃣ 内嵌字幕检测] ──→ 检测到字幕流 ──→ 直接提取（准确度最高）
    ↓ 未检测到
[2️⃣ 烧录字幕检测] ──→ RapidOCR 采样帧识别 ──→ 检测到文字 ──→ 全视频 OCR 提取
    ↓ 未检测到
[3️⃣ 语音转录] ──→ FunASR（中文优化）/ Whisper（多语言）
    ↓
输出 SRT 字幕
```

### 提取方式对比

| 层级 | 方法 | 适用场景 | 准确度 | 速度 |
|------|------|---------|--------|------|
| **L1** | 内嵌字幕提取 | 视频自带字幕流 | ⭐⭐⭐⭐⭐ | ⚡ 极快 |
| **L2** | RapidOCR 烧录识别 | 字幕烧录在画面中 | ⭐⭐⭐⭐ | 🚀 快 |
| **L3** | FunASR Nano | 中文语音转录 | ⭐⭐⭐⭐ | 🐢 中等 |
| **L3** | Whisper | 英文/多语言语音 | ⭐⭐⭐ | 🐢 中等 |

### 技术栈说明

- **RapidOCR (ONNX)**: 用于检测和提取烧录在视频画面中的字幕
  - 🚀 轻量级：ONNX Runtime 推理，无需 GPU
  - 🎯 跨平台：Windows/Linux/Mac 均支持
  - 📦 易部署：单 pip 安装，无复杂依赖
  - ✨ 高精度：基于 PaddleOCR 模型优化

- **FunASR Nano**: 阿里开源中文语音识别模型
  - 🚀 轻量级：~100MB vs Whisper Large ~1.5GB
  - 🎯 中文优化：针对中文语音专门训练，效果优于 Whisper
  - ⏱️ 时间戳：支持字级别时间戳
  - 💨 速度快：CPU 上也能快速运行

## 📊 三维度分析框架

### 1. TextContent Analysis（文本内容分析）
- 叙事结构拆解
- 修辞手法识别
- 关键词提取

### 2. Viral-Abstract-Script（病毒传播框架）
- **Viral-5D 诊断**：Hook / Emotion / 爆点 / CTA / 社交货币
- 风格定位
- 优化建议

### 3. Brainstorming（头脑风暴框架）
- 核心价值拆解
- 2-3 种创意方向探索
- 增量验证点

## 📁 项目结构

```
video-copy-analyzer/
├── SKILL.md                          # 核心技能说明
├── scripts/
│   ├── download_douyin.py            # 抖音视频下载（无水印）
│   ├── extract_subtitle_funasr.py    # 智能字幕提取（FunASR + RapidOCR）
│   ├── extract_subtitle.py           # 基于 Whisper 的提取
│   ├── transcribe_audio.py           # 音频转录脚本
│   └── check_environment.py          # 环境检测脚本
└── references/
    └── analysis-frameworks.md        # 分析框架详解
```

## 🔧 配置说明

首次使用时，skill 会引导你设置默认输出目录：

- **选项 A**：使用默认目录 `~/video-analysis/`
- **选项 B**：每次手动指定
- **选项 C**：设置一个固定的自定义目录

### 分析模型可选项（Step 2）

`step2_analyzer.py` 现支持多提供商切换（Claude/OpenAI/Kimi/Qwen/MiniMax），通过 `.env` 配置：

```bash
# 选择分析提供商:
# anthropic / openai / kimi / qwen / minimax / auto
# auto = 按顺序自动尝试所有 provider
ANALYSIS_PROVIDER=anthropic

# 可选：手动指定降级顺序（不填则默认按其余 provider 自动补齐）
ANALYSIS_FALLBACKS=openai,kimi,qwen,minimax,anthropic

# 可选：模型都失败时是否允许本地兜底
# 1=允许(报告会偏简单) / 0=禁止(直接报错，避免低质量报告)
ALLOW_LOCAL_FALLBACK=0

# 各提供商模型（按需配置）
ANTHROPIC_MODEL=claude-3-5-sonnet-latest
OPENAI_MODEL=gpt-4o-mini
KIMI_MODEL=moonshot-v1-8k
QWEN_MODEL=qwen-plus
MINIMAX_MODEL=MiniMax-Text-01

# 各提供商 API Key
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
KIMI_API_KEY=...
QWEN_API_KEY=...
MINIMAX_API_KEY=...

# 各提供商 Base URL（一般保留默认）
OPENAI_BASE_URL=https://api.openai.com/v1
KIMI_BASE_URL=https://api.moonshot.cn/v1
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MINIMAX_BASE_URL=https://api.minimax.chat/v1
```

说明：
- 不同提供商使用各自 API Key：`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `KIMI_API_KEY` / `QWEN_API_KEY` / `MINIMAX_API_KEY`
- 分析日志会写入 `workspace_data/analysis_debug_<timestamp>.log`

### 达人主页真实点击模式（Step 1）

`step3_batch.py` 会自动识别达人主页链接（`/user/profile/`），并执行：

`点击卡片 -> 采集当前笔记 -> 返回主页 -> 下一条`

可通过环境变量控制单个达人最多采集条数：

```bash
PROFILE_MAX_ITEMS=10
```

## 📄 输出文件

分析完成后，你将获得：

| 文件 | 内容 |
|------|------|
| `{视频ID}.mp4` | 原始视频 |
| `{视频ID}.srt` | 原始字幕 |
| `{视频ID}_文字稿.md` | 校正后文字稿 |
| `{视频ID}_分析报告.md` | 三维度分析报告 |

## 🎯 支持环境

这是一个 **Claude Skill**，可在以下 AI 编程助手中使用：

| 环境 | 模型 | 状态 |
|------|------|------|
| **Antigravity** | Gemini 3 Pro | ✅ 支持 |
| **Cursor** | Claude 4.5 Opus | ✅ **已测试，推荐** |
| **Claude Code** | Claude 4.5 Opus | ✅ 支持 |
| **Windsurf** | 任意 Claude 模型 | ✅ 支持 |
| **Trae** | Claude 3.5/4 | ✅ 支持 |

> 💡 **最佳效果**：在 **Claude 4.5 Opus** 下测试，转录校正和三维度分析效果理想。

## 📝 许可证

MIT License
