import os
import sys
import json
import re
import glob
import time
from datetime import datetime
from dotenv import load_dotenv
from notion_client import Client

from utils import PROJECT_ROOT, WORK_DIR, parse_number

# 加载环境
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None


def check_existing_in_notion(url):
    """Check if a video URL already exists in the Notion database. Returns True if duplicate."""
    if not notion or not NOTION_DATABASE_ID:
        return False
    try:
        results = notion.databases.query(
            database_id=NOTION_DATABASE_ID,
            filter={
                "property": "URL链接",
                "url": {"equals": url}
            },
            page_size=1,
        )
        if results.get("results"):
            return True
    except Exception:
        # If filter fails (e.g., property doesn't exist), skip dedup silently
        pass
    return False


def push_to_notion(meta, analysis_data):
    if not notion:
        print("❌ NOTION_TOKEN 未配置，跳过上传。")
        return
    if not NOTION_DATABASE_ID:
        print("❌ NOTION_DATABASE_ID 未配置，跳过上传。")
        return

    title = meta.get('title', '无标题')

    # Dedup check
    video_url = meta.get('url', '')
    if video_url and check_existing_in_notion(video_url):
        print(f"⏭️ 已存在于 Notion，跳过: {title[:30]}...")
        return

    print(f"📝 正在上报数据: {title[:20]}...")

    analysis = analysis_data['analysis']
    transcript = analysis_data['transcript']
    images = analysis_data['visual_images']
    duration = analysis_data['duration']
    cover_url_public = analysis_data.get('cover_url_public')

    def trim(t, l=1900): return t[:l] + "..." if t and len(str(t))>l else str(t)

    hashtags = re.findall(r"#(\w+)", meta.get('desc', ''))
    keywords_str = ", ".join(hashtags) if hashtags else ""
    iso_date = datetime.now().isoformat()
    try:
        if meta.get('pub_time'):
            dt = datetime.strptime(meta['pub_time'], '%Y-%m-%d %H:%M')
            iso_date = dt.isoformat()
    except Exception:
        pass

    likes = parse_number(meta['stats']['likes'])
    collects = parse_number(meta['stats']['collects'])
    comments = parse_number(meta['stats']['comments'])

    collect_ratio = round((collects / likes) * 100, 1) if likes > 0 else 0
    fire_mark = "🔥" if collect_ratio > 50 else ""
    stats_str = f"👍{likes} | ⭐️{collects} ({collect_ratio}%){fire_mark} | 💬{comments}"

    combined_insight = f"【争吵点】：{analysis.get('comment_basic', '无')}\n\n【深度洞察】：{analysis.get('hot_comment_deep', '无')}"

    # 映射 Notion 字段
    properties = {
        "作者": {"rich_text": [{"text": {"content": meta.get('author', 'Unknown')}}]},
        "视频标题": {"title": [{"text": {"content": title}}]},
        "视频标签": {"rich_text": [{"text": {"content": analysis.get('niche', '')}}]},
        "视频时长": {"rich_text": [{"text": {"content": duration}}]},
        "发布时间": {"date": {"start": iso_date}},
        "关键词": {"rich_text": [{"text": {"content": keywords_str}}]},
        "URL链接": {"url": video_url},
        "赞": {"number": likes},
        "藏": {"number": collects},
        "评": {"number": comments},
        "互动数据": {"rich_text": [{"text": {"content": stats_str}}]},
        "口播文案": {"rich_text": [{"text": {"content": trim(transcript)}}]},
        "页面文案": {"rich_text": [{"text": {"content": trim(meta['desc'])}}]},
        "亮点总结": {"rich_text": [{"text": {"content": analysis.get('highlights', '')}}]},
        "封面分析": {"rich_text": [{"text": {"content": analysis.get('cover_analysis', '无')}}]},
        "赛道": {"rich_text": [{"text": {"content": analysis.get('niche', '')}}]},
        "人群标签": {"rich_text": [{"text": {"content": analysis.get('target_audience', '')}}]},
        "前三秒钩子": {"rich_text": [{"text": {"content": analysis.get('hook_3s', '')}}]},
        "金句钩子": {"rich_text": [{"text": {"content": analysis.get('golden_sentence', '')}}]},
        "核心结构": {"rich_text": [{"text": {"content": analysis.get('structure', '')}}]},
        "结构化分析": {"rich_text": [{"text": {"content": analysis.get('structure', '')}}]},
        "情绪走向": {"rich_text": [{"text": {"content": analysis.get('emotion_arc', '')}}]},
        "拍摄形式": {"rich_text": [{"text": {"content": analysis.get('visual_form', '')}}]},
        "不可替代性": {"rich_text": [{"text": {"content": analysis.get('why_him', '')}}]},
        "热评洞察": {"rich_text": [{"text": {"content": trim(combined_insight)}}]},
        "热评分析": {"rich_text": [{"text": {"content": trim(combined_insight)}}]},
        "选题金矿": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "平台信号": {"rich_text": [{"text": {"content": analysis.get('platform_signal', '')}}]},
        "效果打分": {"rich_text": [{"text": {"content": analysis.get('score_breakdown', '')}}]},
        "评级": {"rich_text": [{"text": {"content": analysis.get('grade', '')}}]},
        "通用公式": {"rich_text": [{"text": {"content": analysis.get('universal_formula', '')}}]},
        "我的选题": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "灵感启示": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "拒绝方向": {"rich_text": [{"text": {"content": analysis.get('refuse_direction', '')}}]},
        "可抄作业": {"rich_text": [{"text": {"content": analysis.get('can_copy', '')}}]},
        "避坑指南": {"rich_text": [{"text": {"content": analysis.get('cannot_copy', '')}}]},
        "一句复用": {"rich_text": [{"text": {"content": analysis.get('reusable_sentence', '')}}]},
    }

    children = [
        {"object": "block", "type": "callout", "callout": {"rich_text": [{"text": {"content": f"🎯 评级：{analysis.get('grade')} | 得分：{analysis.get('score_breakdown')}\n📊 互动：{stats_str}"}}], "icon": {"emoji": "📊"}}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "🖼️ 封面视觉拆解"}}]}},
    ]
    if cover_url_public:
        children.append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": cover_url_public}}})
    children.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": analysis.get('cover_analysis','')}}]}})

    children.extend([
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "1️⃣ 战术拆解 (7步法)"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"🎣 Hook：{analysis.get('hook_3s','')}\n🪙 金句：{analysis.get('golden_sentence','')}\n🏗️ 结构：{analysis.get('structure','')}\n🎭 情绪：{analysis.get('emotion_arc','')}\n📹 形式：{analysis.get('visual_form','')}\n👤 不可替代性：{analysis.get('why_him','')}"}}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "2️⃣ 战略洞察 (运营视角)"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"🗣️ 热评综合：\n{combined_insight}\n\n📡 信号：{analysis.get('platform_signal','')}\n👥 人群：{analysis.get('target_audience','')}"}}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "3️⃣ 选题反推"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"📐 公式：{analysis.get('universal_formula','')}\n🚀 选题：\n{analysis.get('my_new_topics','')}\n🚫 拒绝：{analysis.get('refuse_direction','')}"}}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "4️⃣ 抄作业指南"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": f"✅ 能抄：{analysis.get('can_copy','')}\n❌ 不能抄：{analysis.get('cannot_copy','')}\n♻️ 复用：{analysis.get('reusable_sentence','')}"}}]}},
        {"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "📄 口播文案"}}]}},
        {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": trim(transcript, 1000)}}]}}
    ])

    if images:
        children.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"text": {"content": "🎞️ 关键分镜"}}]}})
        for url in images[:3]:
            children.append({"object": "block", "type": "image", "image": {"type": "external", "external": {"url": url}}})

    try:
        notion.pages.create(parent={"database_id": NOTION_DATABASE_ID}, properties=properties, children=children)
        print(f"✅ Notion 写入成功！")
    except Exception as e:
        print(f"❌ Notion 写入失败: {e}")

def main():
    print("🚀 启动 [批量上报] 模式...")

    if not notion:
        print("❌ NOTION_TOKEN 未配置，无法上传。请在 .env 中配置 NOTION_TOKEN。")
        return

    # 找到所有的 analysis_xxx.json 文件
    analysis_files = glob.glob(os.path.join(WORK_DIR, "analysis_*.json"))

    if not analysis_files:
        print("❌ 未找到分析报告。请先运行 Step 2 (分析)！")
        return

    print(f"📋 发现 {len(analysis_files)} 份待上报报告...")

    uploaded = 0
    skipped = 0
    for i, analysis_path in enumerate(analysis_files):
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)

            # 找到对应的 meta 文件 (为了补全作者等信息)
            meta_path = analysis_data.get('meta_file_path')
            if not meta_path or not os.path.exists(meta_path):
                print(f"⚠️ 找不到关联的 Meta 文件: {meta_path}，跳过。")
                skipped += 1
                continue

            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

            print(f"\n📤 [任务 {i+1}/{len(analysis_files)}] 上报中: {os.path.basename(analysis_path)}")
            push_to_notion(meta, analysis_data)
            uploaded += 1

        except Exception as e:
            print(f"❌ 上报失败: {e}")

        time.sleep(1)

    print(f"\n🎉 上报完毕！成功: {uploaded}, 跳过: {skipped}, 总计: {len(analysis_files)}")

if __name__ == "__main__":
    main()
