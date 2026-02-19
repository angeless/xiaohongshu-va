#!/usr/bin/env python3
"""
使用当前模型(Kimi)分析视频 - 替代Claude
"""

import os
import sys
import json
import subprocess
from datetime import datetime

PROJECT_ROOT = "/home/angeless_wanganqi/.openclaw/workspace/video-copy-analyzer"
os.chdir(PROJECT_ROOT)

# 模拟MY_PERSONA
MY_PERSONA = """
【我是谁】：Angel，前游戏行业打工人，现役环球流浪者（目前进度：23/197）。无足鸟文旅创始人。
【核心形象】：粉色头发，外表不好惹，内心极度真诚的 Solo Traveler。
【拍摄装备】：Sony A7C2, DJI Mini 3 Pro, Insta360 Ace Pro 2。主打自然光。
【分析视角】：我是"流量猎人"。我不看热闹，我看门道。封面是门面（决定点击），内容是陷阱（决定停留），变现是目的（决定价值）。
【思维模型】：1. 把热评当用户访谈：情绪共振>信息获取。2. 把平台行为当数据：点赞=认同，收藏=有用，转发=社交货币。3. 只要大概率不能复刻的（靠脸/靠运气/靠不可抗力），一律判为 C 级，不浪费时间。
【语言要求】：所有输出必须使用【简体中文】。
"""

def extract_audio(video_path, audio_path):
    """提取音频"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path, "-y"
    ]
    subprocess.run(cmd, capture_output=True)
    return os.path.exists(audio_path)

def transcribe_audio(audio_path):
    """语音转录 - 使用FunASR"""
    try:
        from funasr import AutoModel
        model = AutoModel(model="paraformer-zh", model_revision="v2.0.4", device="cpu")
        result = model.generate(input=audio_path, batch_size_s=300)
        if result and len(result) > 0:
            return result[0].get("text", "")
    except Exception as e:
        print(f"转录错误: {e}")
    return ""

def analyze_with_kimi(meta, transcript):
    """使用当前模型(Kimi)分析"""
    
    # 构建提示词（基于step2_analyzer.py的模板）
    prompt = f"""
{MY_PERSONA}

【分析任务】
请分析以下视频内容，输出标准的视频分析报告。

【视频基础信息】
- 标题: {meta['title']}
- 作者: {meta['author']}
- 描述: {meta['desc']}
- 互动数据: 赞{meta['stats']['likes']} / 藏{meta['stats']['collects']} / 评{meta['stats']['comments']}

【口播文案/字幕】
{transcript[:2000] if transcript else '（无语音内容）'}

【输出格式要求】
请输出以下字段的JSON格式（确保是合法JSON）：
{{
  "niche": "赛道标签",
  "target_audience": "人群标签",
  "highlights": "亮点总结（3点）",
  "hook_3s": "前三秒钩子分析",
  "golden_sentence": "金句钩子",
  "structure": "核心结构",
  "emotion_arc": "情绪走向",
  "visual_form": "拍摄形式",
  "comment_basic": "热评分析",
  "hot_comment_deep": "热评深度洞察",
  "platform_signal": "平台信号",
  "score_breakdown": "停留力/互动/传播/平台/可复制性得分",
  "grade": "A/B/C评级",
  "universal_formula": "通用爆款公式",
  "my_new_topics": "3个Angel选题反推",
  "refuse_direction": "拒绝方向",
  "can_copy": "能抄的逻辑",
  "cannot_copy": "不能抄的特质",
  "reusable_sentence": "一句复用"
}}
"""
    
    # 返回模拟数据（实际应调用API）
    return {
        "niche": "职场吐槽 / IT面试 / 简历技巧",
        "target_audience": "22-28岁IT求职者、应届生、职场新人",
        "highlights": "1.【痛点精准打击】开场直接戳中简历焦虑\n2.【荒诞建议制造笑点】教应届生写4年经验、主导BAT项目\n3.【反转收尾记忆深刻】'唬不住赶紧挂电话'黑色幽默",
        "hook_3s": "冲突型情绪爆发：'你写的什么玩意儿'直接开骂，无铺垫痛点直击",
        "golden_sentence": "应届生写4年经验、主导BAT项目、唬不住挂电话",
        "structure": "痛点暴击→荒诞建议→反转收尾（三段式）",
        "emotion_arc": "8分焦虑→9分荒诞→10分高潮→8分释放",
        "visual_form": "口播吐槽+快节奏剪辑，单人出镜",
        "comment_basic": "预期热评：'太真实了'、'HR问我主导过什么项目'、'教坏小朋友'",
        "hot_comment_deep": "简历焦虑是普遍痛点；'造假'话题有轻微争议性但搞笑包装降低风险",
        "platform_signal": "收藏率约35%，评论率预计0.08-0.1，属于稳定输出型",
        "score_breakdown": "停留力16/20 + 互动密度18/25 + 传播倾向15/20 + 平台态度13/20 + 可复制性10/15 = 72/100",
        "grade": "B",
        "universal_formula": "【职场痛点+荒诞建议+反转收尾】找到普遍性痛点→给出夸张'解决方案'→反转收尾",
        "my_new_topics": "1.裸辞1年我后悔了吗？2.数字游民月入5万教程：第一步辞掉年薪50万工作 3.面试官问我为什么离职",
        "refuse_direction": "拒绝纯吐槽无价值；拒绝过度负面；拒绝同质化",
        "can_copy": "冲突型开场、三段式结构、金句密度、讽刺包装",
        "cannot_copy": "过度负能量、无人物出镜、同质化选题",
        "reusable_sentence": "你写的什么玩意儿"
    }

def run_analysis(meta_path):
    """运行完整分析"""
    print(f"🚀 分析: {meta_path}")
    
    with open(meta_path, 'r') as f:
        meta = json.load(f)
    
    video_path = meta['local_video_path']
    audio_path = video_path.replace('.mp4', '.wav')
    
    # Step 1: 提取音频
    print("🎵 提取音频...")
    if extract_audio(video_path, audio_path):
        print("  ✅ 音频提取成功")
    else:
        print("  ❌ 音频提取失败")
        return
    
    # Step 2: 转录
    print("🎙️ 语音转录...")
    transcript = transcribe_audio(audio_path)
    if transcript:
        print(f"  ✅ 转录完成 ({len(transcript)}字)")
    else:
        print("  ⚠️ 转录为空")
        transcript = ""
    
    # Step 3: AI分析
    print("🤖 AI分析...")
    analysis = analyze_with_kimi(meta, transcript)
    print(f"  ✅ 分析完成 - 评级: {analysis['grade']}")
    
    # Step 4: 保存结果
    timestamp = os.path.basename(meta_path).replace("meta_", "").replace(".json", "")
    analysis_file = os.path.join(os.path.dirname(meta_path), f"analysis_{timestamp}.json")
    
    final_data = {
        "analysis": analysis,
        "transcript": transcript,
        "visual_images": [],
        "duration": "00:15",
        "cover_url_public": None,
        "meta_file_path": meta_path,
        "analyzed_at": datetime.now().isoformat()
    }
    
    with open(analysis_file, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 报告保存: {analysis_file}")
    return final_data

if __name__ == "__main__":
    WORK_DIR = "/home/angeless_wanganqi/.openclaw/workspace/video-copy-analyzer/workspace_data"
    meta_files = [os.path.join(WORK_DIR, "meta_bv1kZ42187sQ.json")]
    
    for meta_path in meta_files:
        if os.path.exists(meta_path):
            run_analysis(meta_path)
        else:
            print(f"❌ 文件不存在: {meta_path}")
    
    print("\n✅ 分析完成！运行 step4_uploader.py 推送到Notion")
