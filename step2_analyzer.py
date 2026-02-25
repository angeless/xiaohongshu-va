import os
import sys
import json
import warnings
import whisper
import cv2
import requests
import base64
import re
import glob
import time
import traceback
import numpy as np
from datetime import datetime
from dotenv import load_dotenv

try:
    import anthropic
except ImportError:
    anthropic = None

# 忽略警告
warnings.filterwarnings("ignore")

# 加载环境（固定使用脚本所在目录，避免从其他目录启动时读不到 .env）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))


def env_clean(name, default=None):
    """读取并清洗 .env 值，容忍尾部注释和包裹引号。"""
    value = os.getenv(name, default)
    if value is None:
        return None
    value = str(value).strip()
    # 允许 value 后追加注释：KEY=value  # comment
    value = re.sub(r"\s+#.*$", "", value).strip()
    # 容忍单边或双边引号污染
    value = value.strip().strip('"').strip("'").strip()
    return value

# 🔥🔥🔥 引入救星库 (核心修复) 🔥🔥🔥
try:
    from json_repair import repair_json
except ImportError:
    print("❌ 严重错误：缺少必要库！请立即运行终端命令：")
    print("👉 pip install json_repair")
    sys.exit(1)

WORK_DIR = os.path.join(PROJECT_ROOT, "workspace_data")
os.makedirs(WORK_DIR, exist_ok=True)

# Anthropic 客户端按需初始化，避免非 Claude 模式下硬依赖
client_claude = None
anthropic_api_key = env_clean("ANTHROPIC_API_KEY")
if anthropic and anthropic_api_key:
    try:
        client_claude = anthropic.Anthropic(
            api_key=anthropic_api_key,
            timeout=300.0,
            max_retries=2
        )
    except Exception:
        client_claude = None

# ==========================================
# 👇 【Angel 的灵魂 - 100% 满血未删减版】
# ==========================================
MY_PERSONA = """
【我是谁】：Angel，前游戏行业打工人，现役环球流浪者（目前进度：23/197）。无足鸟文旅创始人。
【核心形象】：粉色头发，外表不好惹，内心极度真诚的 Solo Traveler。
【拍摄装备】：Sony A7C2, DJI Mini 3 Pro, Insta360 Ace Pro 2。主打自然光。
【分析视角】：
我是“流量猎人”。我不看热闹，我看门道。
封面是门面（决定点击），内容是陷阱（决定停留），变现是目的（决定价值）。
【思维模型】：
1. 把热评当用户访谈：情绪共振>信息获取。
2. 把平台行为当数据：点赞=认同，收藏=有用，转发=社交货币。
3. 只要大概率不能复刻的（靠脸/靠运气/靠不可抗力），一律判为 C 级，不浪费时间。
【语言要求】：所有输出必须使用【简体中文】。
"""

# ==========================================
# 👇 工具函数
# ==========================================

def parse_number(text):
    if not text: return 0
    text = str(text).strip().lower()
    try:
        text = text.replace('+', '')
        if '万' in text: return int(float(text.replace('万', '')) * 10000)
        elif 'w' in text: return int(float(text.replace('w', '')) * 10000)
        elif 'k' in text: return int(float(text.replace('k', '')) * 1000)
        else:
            clean_text = re.sub(r'[^\d.]', '', text)
            return int(float(clean_text)) if clean_text else 0
    except: return 0


def generate_local_fallback_analysis(meta, transcript, reason):
    """当所有模型都不可用时，生成可读的本地兜底报告。"""
    likes = parse_number(meta.get("stats", {}).get("likes", 0))
    collects = parse_number(meta.get("stats", {}).get("collects", 0))
    comments = parse_number(meta.get("stats", {}).get("comments", 0))
    total = likes + collects + comments

    if total >= 50000:
        grade = "A"
    elif total >= 5000:
        grade = "B"
    else:
        grade = "C"

    desc = (meta.get("desc") or "").strip()
    transcript = (transcript or "").strip()
    preview = transcript[:280] if transcript else "（未获取到有效转录文本）"
    hook_guess = "这个视频前三秒靠【画面冲击/标题信息密度】留住用户（本地估计）"
    niche_guess = "旅行Vlog" if any(x in desc for x in ["旅行", "vlog", "环球", "自驾"]) else "泛生活记录"

    reason_short = str(reason)[:300] if reason else "模型不可用"
    score = (
        f"停留力: 12/20 | 互动密度: 15/25 | 传播倾向: 12/20 | "
        f"平台态度: 10/20 | 可复制性: 10/15 | 总评: {grade}（本地估计）"
    )

    return {
        "niche": niche_guess,
        "target_audience": "对旅行/生活方式感兴趣的短视频用户（本地估计）",
        "highlights": (
            "1. 主题表达清晰，内容方向明确。\n"
            "2. 具备可复用的开场-展开-收束结构。\n"
            "3. 有一定互动基础，具备优化空间。"
        ),
        "cover_analysis": "封面分析降级为本地模式：建议突出人物主体+地点关键词+结果导向文案。",
        "hook_3s": hook_guess,
        "golden_sentence": "建议把核心观点前置成一句“可记忆短句”（本地估计）。",
        "structure": "大致为【场景引入 -> 过程记录 -> 个人观点/结论】（本地估计）",
        "emotion_arc": "情绪曲线以平稳叙述为主，中段出现信息峰值（本地估计）",
        "visual_form": "Vlog/口播混合（本地估计）",
        "comment_basic": "评论区数据未深挖，建议重点看争议与共鸣关键词。",
        "why_him": "具有人设驱动特征，但需结合更多样本判断不可替代性。",
        "hot_comment_deep": "热评深度分析降级（模型不可用），建议后续补跑。",
        "platform_signal": f"点赞:{likes} 收藏:{collects} 评论:{comments}（来自抓取）",
        "score_breakdown": score,
        "grade": grade,
        "universal_formula": "强开场 + 明确冲突/信息点 + 可执行结论",
        "my_new_topics": "1) 同题材反差切入 2) 低成本复现路线 3) 个人经验拆解",
        "refuse_direction": "避免纯情绪堆砌、无信息增量的流水账表达。",
        "reusable_sentence": "把可复用方法说清楚，比讲感受更容易带来收藏。",
        "can_copy": "结构节奏、信息组织方式、开场表达。",
        "cannot_copy": "个人经历与天然人设红利。",
        "_fallback_reason": reason_short,
        "_fallback_preview": preview,
    }


def make_logger(log_file):
    def _log(message):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {message}"
        print(line)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
    return _log


def get_provider_configs():
    return {
        "anthropic": {
            "model": env_clean("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            "api_key": env_clean("ANTHROPIC_API_KEY"),
            "base_url": None,
        },
        "openai": {
            "model": env_clean("OPENAI_MODEL", "gpt-4o-mini"),
            "api_key": env_clean("OPENAI_API_KEY"),
            "base_url": env_clean("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        },
        "kimi": {
            "model": env_clean("KIMI_MODEL", "moonshot-v1-8k"),
            "api_key": env_clean("KIMI_API_KEY"),
            "base_url": env_clean("KIMI_BASE_URL", "https://api.moonshot.cn/v1"),
        },
        "qwen": {
            "model": env_clean("QWEN_MODEL", "qwen-plus"),
            "api_key": env_clean("QWEN_API_KEY"),
            "base_url": env_clean("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        },
        "minimax": {
            "model": env_clean("MINIMAX_MODEL", "MiniMax-Text-01"),
            "api_key": env_clean("MINIMAX_API_KEY"),
            "base_url": env_clean("MINIMAX_BASE_URL", "https://api.minimax.chat/v1"),
        },
    }


def get_provider_config(provider=None):
    provider = (provider or os.getenv("ANALYSIS_PROVIDER", "anthropic")).strip().lower()
    configs = get_provider_configs()
    return provider, configs.get(provider)


def get_supported_providers():
    return ["anthropic", "openai", "kimi", "qwen", "minimax"]


def build_provider_chain():
    primary = os.getenv("ANALYSIS_PROVIDER", "anthropic").strip().lower()
    supported = get_supported_providers()

    if primary == "auto":
        chain = list(supported)
    else:
        if primary not in supported:
            primary = "anthropic"
        default_fallbacks = ",".join([p for p in supported if p != primary])
        fallback_raw = os.getenv("ANALYSIS_FALLBACKS", default_fallbacks)
        fallback_list = [p.strip().lower() for p in fallback_raw.split(",") if p.strip()]
        chain = [primary] + fallback_list

    # 去重 + 过滤未知 provider
    dedup = []
    seen = set()
    for p in chain:
        if p in supported and p not in seen:
            seen.add(p)
            dedup.append(p)
    return dedup

def clean_hybrid_response(raw_text):
    """🔥 核武器级修复：使用 json_repair 自动纠正语法错误"""
    if not raw_text: return {}
    
    print("🧹 正在调用 json_repair 进行智能修复...")
    
    # 1. 先剥离 Markdown 代码块标记
    text = re.sub(r'```[a-zA-Z]*\s*', '', raw_text, flags=re.IGNORECASE)
    text = re.sub(r'```', '', text).strip()
    
    # 2. 截取 JSON 主体 (防止首尾有废话)
    start_idx = text.find('{')
    end_idx = text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        text = text[start_idx : end_idx + 1]
    
    # 3. 调用神器进行修复
    try:
        # repair_json 会自动处理未转义的引号、缺少的逗号等
        parsed_json = json.loads(repair_json(text))
        return parsed_json
    except Exception as e:
        print(f"❌ 解析彻底失败: {e}")
        return None

def upload_to_imgbb(image_path, log=None):
    api_key = os.getenv("IMGBB_API_KEY")
    if not api_key:
        if log:
            log("⚠️ IMGBB_API_KEY 未配置，跳过外链上传。")
        return None
    try:
        with open(image_path, "rb") as file:
            res = requests.post("https://api.imgbb.com/1/upload", data={"key": api_key}, files={"image": file}, timeout=30)
            data = res.json()
            if data.get('success'):
                return data['data']['url']
            if log:
                log(f"⚠️ imgbb 上传失败: {data}")
    except Exception as e:
        if log:
            log(f"⚠️ imgbb 上传异常: {e}")
    return None

def download_cover_image(url, save_dir, log=None):
    if not url:
        return None
    try:
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            filename = f"cover_{int(datetime.now().timestamp())}.jpg"
            path = os.path.join(save_dir, filename)
            image_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if img is None:
                if log:
                    log("⚠️ 封面下载成功但解码失败。")
                return None
            cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if log:
                log(f"✅ 封面图片已保存: {path}")
            return path
        if log:
            log(f"⚠️ 封面下载状态异常: {response.status_code}")
    except Exception as e:
        if log:
            log(f"⚠️ 封面下载异常: {e}")
    return None

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def extract_visuals(video_path, log=None):
    if log:
        log("👁️ [Vision] 正在进行智能分镜分析...")
    image_urls = []
    duration_str = "00:00"
    try:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps > 0:
            duration_str = f"{int(total/fps)//60:02d}:{int(total/fps)%60:02d}"
        count = 0
        saved_count = 0
        prev_hist = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            count += 1
            if count % 15 != 0:
                continue
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
            cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
            is_new = False
            if prev_hist is None or cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA) > 0.4:
                is_new = True
            if is_new:
                path = f"workspace_data/frame_{saved_count}.jpg"
                cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                link = upload_to_imgbb(path, log=log)
                if link:
                    image_urls.append(link)
                saved_count += 1
                prev_hist = hist
            if saved_count >= 6:
                break
        cap.release()
        if log:
            log(f"✅ [Vision] 分镜提取完成，上传图片 {len(image_urls)} 张，时长 {duration_str}")
    except Exception as e:
        if log:
            log(f"❌ [Vision] 分镜提取失败: {e}\n{traceback.format_exc()}")
    return image_urls, duration_str


def _extract_content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))
                elif isinstance(item.get("text"), str):
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def call_anthropic_model(messages_content, model_name, log=None):
    if not client_claude:
        raise RuntimeError("Anthropic 客户端不可用，请检查 anthropic 包和 ANTHROPIC_API_KEY。")
    if log:
        log(f"🧠 [Brain] 使用 Anthropic 模型: {model_name}")
    msg = client_claude.messages.create(
        model=model_name,
        max_tokens=4096,
        messages=[{"role": "user", "content": messages_content}]
    )
    raw = "".join([b.text for b in msg.content if getattr(b, "type", "") == "text"])
    return raw


def call_openai_compatible_model(provider, model_name, api_key, base_url, text_prompt, cover_base64=None, log=None):
    if not api_key:
        raise RuntimeError(f"{provider} 未配置 API Key。")
    if not base_url:
        raise RuntimeError(f"{provider} 未配置 base_url。")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    def _build_payload(with_image):
        if with_image and cover_base64:
            content = [
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cover_base64}"}},
            ]
        else:
            content = text_prompt
        return {
            "model": model_name,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 4096,
            "temperature": 0.3,
        }

    if log:
        log(f"🧠 [Brain] 使用 {provider} 模型: {model_name}")

    with_image = bool(cover_base64)
    for attempt in range(2):
        payload = _build_payload(with_image=with_image)
        response = requests.post(endpoint, headers=headers, json=payload, timeout=300)
        if response.status_code >= 400:
            msg = response.text[:500]
            if with_image and attempt == 0:
                if log:
                    log(f"⚠️ {provider} 图像输入失败，自动降级为文本重试: {response.status_code} {msg}")
                with_image = False
                continue
            raise RuntimeError(f"{provider} API 错误: {response.status_code} {msg}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"{provider} API 返回无 choices: {data}")
        raw = _extract_content_text(choices[0].get("message", {}).get("content", ""))
        if raw:
            return raw
        raise RuntimeError(f"{provider} API 返回内容为空: {data}")

    raise RuntimeError(f"{provider} 调用失败。")

# ==========================================
# 👇 核心分析逻辑 (Prompt 完全恢复不删减)
# ==========================================

def _invoke_provider(provider, cfg, messages_content, text_prompt, cover_base64, log=None):
    if provider == "anthropic":
        return call_anthropic_model(
            messages_content=messages_content,
            model_name=cfg["model"],
            log=log,
        )
    return call_openai_compatible_model(
        provider=provider,
        model_name=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        text_prompt=text_prompt,
        cover_base64=cover_base64,
        log=log,
    )


def analyze_content(meta, transcript, cover_base64=None, log=None):
    if log:
        log("🧠 [Brain] 开始调用大模型做内容分析...")
    
    likes = parse_number(meta['stats'].get('likes', 0))
    collects = parse_number(meta['stats'].get('collects', 0))
    comments = parse_number(meta['stats'].get('comments', 0))
    ratio_collect_like = round(collects / likes, 2) if likes > 0 else 0
    ratio_comment_like = round(comments / likes, 2) if likes > 0 else 0
    stats_hint = f"收藏/点赞比：{ratio_collect_like} (若>0.5说明工具属性强/干货强)，评论/点赞比：{ratio_comment_like} (若高说明争议大或共鸣强)"

    messages_content = []
    
    # 🔥🔥🔥 100% 满血还原原版 Prompt，包含所有引导语 🔥🔥🔥
    text_prompt = f"""
    【角色设定】
    你是 Angel 的首席内容参谋。请基于【Angel 独家爆款方法论】对视频进行全维度拆解。
    
    【Angel 档案】
    {MY_PERSONA}

    【竞品数据输入】
    1. 标题：{meta['title']}
    2. 作者：{meta['author']}
    3. 原始文案：{meta['desc']}
    4. 互动数据：赞 {likes} | 藏 {collects} | 评 {comments}
    5. 数据洞察：{stats_hint}
    6. 热评 Top5：{meta.get('top_comments', '无')}
    7. 逐字稿：{transcript}
    
    【任务一：封面视觉诊断 (Visual Hook)】
    (请结合传入的封面图片进行分析，若无图片则根据标题推测)
    1. 构图元素：是人像大头？还是场景+人？有无特殊道具？
    2. 花字设计：字体多大？颜色对比度如何？关键词是什么？
    3. 点击诱因：这张图为什么让人想点？(美感/猎奇/焦虑/干货感?)
    
    【任务二：Angel 的 7 步战术拆解 (基础内功)】
    1. 前3秒 Hook：是反常？直接给结果？还是先戳痛点？
       👉 必须输出："这个视频前三秒靠 [具体手段] 留下人"
    2. 钩子金句：只记一句，记哪句？(通常是第一句或字幕最大那句)
    3. 结构类型：是 (问题-共鸣-经历-观点) 还是 (故事-翻转-结论)？
    4. 情绪走向 (0-10分)：一开始几分？中间有无起伏？结尾是安慰/狠话/清醒？
    5. 镜头形式：最省力的特征 (站/坐/对镜/Vlog/旁白)。
    6. 评论吵什么：重复出现的问题或情绪最激烈的点。
    7. 为什么是他拍：换个人成立吗？(强人设 vs 强模板)
    
    【任务三：运营总监级 战略分析 (高阶心法)】
    1. 热评深挖：把评论当做用户访谈。是情绪共振？需求外溢(要后续)？还是价值观争议？
    2. 外部信号：收藏多还是点赞多？是被"用"还是被"认同"？有无二刷/转发信号？
    3. 爆款打分 (总分100)：
       - 停留力 (20)：前3秒是否下意识停住？
       - 互动密度 (25)：评论区是否像日记/活人？
       - 传播倾向 (20)：有理由转给别人吗？
       - 平台态度 (20)：数据是否反常？
       - 可复制性 (15)：Angel 能不能拍？
    4. 评级与行动：
       - 🟢 A级(>80)：必拆，出通用公式，反推3个Angel选题。
       - 🟡 B级(60-79)：参考部分，只学亮点。
       - 🔴 C级(<60)：判定为“无效爆款”或“纯运气”，但必须在【亮点总结】和【结构】中说明它为什么烂，**不可留白**。
       
    【任务四：总结归档】
    1. 亮点总结：精简3点最值得学习的地方。
    2. 赛道标签 & 人群标签 (如：25-30岁焦虑宝妈/精致白领)。
    3. 抄作业：能抄的逻辑 vs 我不能抄的特质。
    4. 选题反推：基于 Angel 人设反推 3 个新选题。

    【输出格式要求】
    1. **只输出纯 JSON**，不要包含 "```json" 等标记。
    2. 即使评级为 C，所有字段也必须填满。
    
    格式模板：
    {{
      "niche": "赛道标签",
      "target_audience": "人群标签",
      "highlights": "1. [原因]...\\n2. ...",
      "cover_analysis": "封面分析...", 
      "hook_3s": "这个视频前三秒靠...",
      "golden_sentence": "钩子金句...",
      "structure": "结构类型...",
      "emotion_arc": "情绪走向...",
      "visual_form": "镜头形式...",
      "comment_basic": "评论争议点...",
      "why_him": "不可替代性分析...",
      "hot_comment_deep": "热评深度洞察...",
      "platform_signal": "平台信号分析...",
      "score_breakdown": "各项打分细节...",
      "grade": "A/B/C",
      "universal_formula": "通用爆款公式...",
      "my_new_topics": "反推3个新选题...",
      "refuse_direction": "拒绝的方向...",
      "reusable_sentence": "一句话复用...",
      "can_copy": "能抄的逻辑...",
      "cannot_copy": "不能抄的特质..."
    }}
    """
    messages_content.append({"type": "text", "text": text_prompt})

    if cover_base64:
        messages_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": cover_base64
            }
        })
    
    allow_local_fallback = os.getenv("ALLOW_LOCAL_FALLBACK", "1") != "0"
    try:
        provider_chain = build_provider_chain()
        if log:
            log(f"🧭 provider 尝试顺序: {provider_chain}")

        last_err = None
        used_provider = None
        used_model = None
        raw = None

        for provider in provider_chain:
            provider, cfg = get_provider_config(provider)
            if not cfg:
                continue
            if provider != "anthropic" and not cfg.get("api_key"):
                if log:
                    log(f"⚠️ 跳过 {provider}：未配置 API Key。")
                continue
            if provider == "anthropic" and (not client_claude or not cfg.get("api_key")):
                if log:
                    log("⚠️ 跳过 anthropic：客户端不可用或未配置 key。")
                continue

            try:
                raw = _invoke_provider(provider, cfg, messages_content, text_prompt, cover_base64, log=log)
                used_provider = provider
                used_model = cfg.get("model")
                break
            except Exception as e:
                last_err = e
                if log:
                    log(f"⚠️ {provider} 调用失败，尝试下一个 provider: {e}")
                continue

        if raw is None:
            if last_err:
                raise last_err
            raise RuntimeError("没有可用的分析 provider（请检查 ANALYSIS_PROVIDER 和各 provider API key）。")
        
        # 🔥 使用神器修复 JSON
        result = clean_hybrid_response(raw)
        
        if not result:
            debug_file = f"debug_error_{int(time.time())}.txt"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(raw)
            if log:
                log(f"❌ JSON 修复后依然解析失败！原始回复已保存至: {debug_file}")
            else:
                print(f"❌ JSON 修复后依然解析失败！原始回复已保存至: {debug_file}")
            if allow_local_fallback:
                if log:
                    log("⚠️ JSON 解析失败，回退到本地兜底分析。")
                local = generate_local_fallback_analysis(meta, transcript, "JSON parse failed")
                return local, "local_fallback", "heuristic-v1"
            return None, None, None
        
        # 兜底 Key 检查
        required_keys = ['highlights', 'structure', 'grade', 'niche']
        for k in required_keys:
            if k not in result: result[k] = "（字段缺失）"
                
        if log:
            log("✅ 大模型分析并修复完成。")
        else:
            print("✅ 大模型分析并修复完成。")
        return result, used_provider, used_model

    except Exception as e:
        if anthropic and isinstance(e, getattr(anthropic, "APIError", Exception)):
            if log:
                log(f"❌ Anthropic API 报错: {e}")
            else:
                print(f"❌ Anthropic API 报错: {e}")
        else:
            if log:
                log(f"❌ 分析调用失败: {e}\n{traceback.format_exc()}")
            else:
                print(f"❌ 未知错误: {e}")
        if allow_local_fallback:
            if log:
                log("⚠️ 模型全部失败，启用本地兜底分析。")
            local = generate_local_fallback_analysis(meta, transcript, str(e))
            return local, "local_fallback", "heuristic-v1"
        return None, None, None

def run_single_analysis(meta_path):
    print(f"🚀 正在分析: {meta_path}")
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    
    base_name = os.path.basename(meta_path)
    timestamp = base_name.replace("meta_", "").replace(".json", "")
    analysis_file = os.path.join(os.path.dirname(meta_path), f"analysis_{timestamp}.json")
    log_file = os.path.join(WORK_DIR, f"analysis_debug_{timestamp}.log")
    log = make_logger(log_file)
    log(f"🧾 分析任务启动: {meta_path}")
    
    # 强制重新分析以应用修复
    # if os.path.exists(analysis_file):
    #     print(f"⏭️ 报告已存在，跳过: {analysis_file}")
    #     return

    log("🖼️ 处理封面图中...")
    cover_base64 = None
    cover_url_public = None
    if meta.get('cover_url'):
        local_cover = download_cover_image(meta['cover_url'], WORK_DIR, log=log)
        if local_cover:
            try:
                cover_base64 = encode_image(local_cover)
                cover_url_public = upload_to_imgbb(local_cover, log=log)
                if not cover_url_public:
                    cover_url_public = meta['cover_url']
                log("✅ 封面图处理完成。")
            except Exception as e:
                log(f"❌ 封面图编码失败: {e}\n{traceback.format_exc()}")
        else:
            log("⚠️ 封面图下载失败，后续按无封面处理。")
    else:
        log("⚠️ meta 中无 cover_url，跳过封面处理。")

    log("👂 [Audio] 开始听写...")
    whisper_model = os.getenv("WHISPER_MODEL", "medium")
    try:
        model = whisper.load_model(whisper_model)
        result = model.transcribe(
            meta['local_video_path'],
            fp16=False,
            language='zh',
            initial_prompt="以下是简体中文的视频文案。"
        )
        transcript = "\n".join(
            [f"[{int(s['start'])//60:02d}:{int(s['start'])%60:02d}] {s['text']}" for s in result.get('segments', [])]
        )
        log(f"✅ [Audio] 听写完成，段落数: {len(result.get('segments', []))}")
    except Exception as e:
        log(f"❌ [Audio] 听写失败: {e}\n{traceback.format_exc()}")
        return
    
    images, duration = extract_visuals(meta['local_video_path'], log=log)
    
    analysis, used_provider, used_model = analyze_content(meta, transcript, cover_base64, log=log)
    
    if not analysis:
        log("❌ 分析失败。")
        return

    final_data = {
        "analysis": analysis,
        "transcript": transcript,
        "visual_images": images,
        "duration": duration,
        "cover_url_public": cover_url_public,
        "meta_file_path": meta_path,
        "analyzed_at": datetime.now().isoformat(),
        "model_provider": used_provider or os.getenv("ANALYSIS_PROVIDER", "anthropic"),
        "model_name": used_model,
        "debug_log_file": log_file,
    }
    
    try:
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        log(f"💾 分析报告已保存: {analysis_file}")
    except Exception as e:
        log(f"❌ 保存失败: {e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    print("🚀 启动 [Step 2: 满血本地分析] 模式...")
    provider = os.getenv("ANALYSIS_PROVIDER", "anthropic").strip().lower()
    chain = build_provider_chain()
    print(f"🧠 当前 provider 配置: ANALYSIS_PROVIDER={provider}, chain={chain}")
    cfgs = get_provider_configs()
    for name in chain:
        cfg = cfgs.get(name, {})
        key_ok = bool(cfg.get("api_key"))
        print(f"   - {name}: model={cfg.get('model')} key={'OK' if key_ok else 'MISSING'}")
    meta_files = glob.glob(os.path.join(WORK_DIR, "meta_*.json"))
    
    if not meta_files:
        print("❌ 未找到数据。请先运行 Step 3 下载！")
        sys.exit()

    print(f"📋 发现 {len(meta_files)} 个任务...")
    for i, json_path in enumerate(meta_files):
        print(f"\n🎬 [任务 {i+1}/{len(meta_files)}]")
        try:
            run_single_analysis(json_path)
        except Exception as e:
            print(f"❌ 任务 {i+1} 异常: {e}")
        time.sleep(5)

    print("\n" + "="*60)
    print("🎉 分析阶段结束！请运行: python3 step4_uploader.py 上报数据")
    print("="*60)
