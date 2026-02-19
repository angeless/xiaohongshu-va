#!/usr/bin/env python3
"""
适配我们数据库结构的Notion推送脚本
"""

import os
import sys
import json
import re
import glob
import ssl
import urllib.request
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('.env.local')

API_KEY = os.getenv("NOTION_TOKEN", "")
CONTENT_DB = os.getenv("NOTION_DATABASE_ID", "")
WORK_DIR = "/home/angeless_wanganqi/.openclaw/workspace/video-copy-analyzer/workspace_data"

def make_request(method, endpoint, data=None):
    url = f"https://api.notion.com/v1{endpoint}"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    
    try:
        context = ssl._create_unverified_context()
        if data:
            req_data = json.dumps(data).encode('utf-8')
            request = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        else:
            request = urllib.request.Request(url, headers=headers, method=method)
        
        with urllib.request.urlopen(request, context=context) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"API错误: {str(e)[:200]}")
        return None

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

def trim(t, l=1900): 
    return t[:l] + "..." if t and len(str(t)) > l else str(t)

def push_to_notion(meta, analysis_data):
    title = meta.get('title', '无标题')
    print(f"📝 上报: {title[:30]}...")
    
    analysis = analysis_data['analysis']
    transcript = analysis_data.get('transcript', '')
    duration = analysis_data.get('duration', '')
    
    # 解析数据
    likes = parse_number(meta['stats']['likes'])
    collects = parse_number(meta['stats']['collects'])
    comments = parse_number(meta['stats']['comments'])
    
    collect_ratio = round((collects / likes) * 100, 1) if likes > 0 else 0
    fire_mark = "🔥" if collect_ratio > 50 else ""
    stats_str = f"👍{likes} | ⭐️{collects} ({collect_ratio}%){fire_mark} | 💬{comments}"
    
    combined_insight = f"【争吵点】：{analysis.get('comment_basic', '无')}\n\n【深度洞察】：{analysis.get('hot_comment_deep', '无')}"
    
    # 构建properties（使用我们的字段名）
    properties = {
        "笔记标题": {"title": [{"text": {"content": title}}]},
        "作者": {"rich_text": [{"text": {"content": meta.get('author', 'Unknown')}}]},
        "发布时间": {"date": {"start": datetime.now().isoformat()}},
        "点赞数": {"number": likes},
        "收藏数": {"number": collects},
        "评论数": {"number": comments},
        "赞": {"number": likes},
        "藏": {"number": collects},
        "评": {"number": comments},
        "互动数据": {"rich_text": [{"text": {"content": stats_str}}]},
        "口播文案": {"rich_text": [{"text": {"content": trim(transcript)}}]},
        "页面文案": {"rich_text": [{"text": {"content": trim(meta.get('desc', ''))}}]},
        "亮点总结": {"rich_text": [{"text": {"content": analysis.get('highlights', '')}}]},
        "赛道": {"rich_text": [{"text": {"content": analysis.get('niche', '')}}]},
        "人群标签": {"rich_text": [{"text": {"content": analysis.get('target_audience', '')}}]},
        "前三秒钩子": {"rich_text": [{"text": {"content": analysis.get('hook_3s', '')}}]},
        "金句钩子": {"rich_text": [{"text": {"content": analysis.get('golden_sentence', '')}}]},
        "核心结构": {"rich_text": [{"text": {"content": analysis.get('structure', '')}}]},
        "结构化分析": {"rich_text": [{"text": {"content": analysis.get('structure', '')}}]},
        "情绪走向": {"rich_text": [{"text": {"content": analysis.get('emotion_arc', '')}}]},
        "拍摄形式": {"rich_text": [{"text": {"content": analysis.get('visual_form', '')}}]},
        "不可替代性": {"rich_text": [{"text": {"content": analysis.get('why_him', '')}}]},
        "热评分析": {"rich_text": [{"text": {"content": trim(combined_insight)}}]},
        "热评洞察": {"rich_text": [{"text": {"content": trim(combined_insight)}}]},
        "平台信号": {"rich_text": [{"text": {"content": analysis.get('platform_signal', '')}}]},
        "效果打分": {"rich_text": [{"text": {"content": analysis.get('score_breakdown', '')}}]},
        "评级": {"rich_text": [{"text": {"content": analysis.get('grade', '')}}]},
        "通用公式": {"rich_text": [{"text": {"content": analysis.get('universal_formula', '')}}]},
        "我的选题": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "选题金矿": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "灵感启示": {"rich_text": [{"text": {"content": analysis.get('my_new_topics', '')}}]},
        "拒绝方向": {"rich_text": [{"text": {"content": analysis.get('refuse_direction', '')}}]},
        "可抄作业": {"rich_text": [{"text": {"content": analysis.get('can_copy', '')}}]},
        "避坑指南": {"rich_text": [{"text": {"content": analysis.get('cannot_copy', '')}}]},
        "一句复用": {"rich_text": [{"text": {"content": analysis.get('reusable_sentence', '')}}]},
        "笔记类型": {"select": {"name": "视频"}},
        "内容分类": {"select": {"name": "干货"}},
    }
    
    # 创建页面
    data = {
        "parent": {"database_id": CONTENT_DB},
        "properties": properties
    }
    
    result = make_request("POST", "/pages", data)
    if result:
        page_id = result.get("id")
        print(f"  ✅ Notion推送成功")
        print(f"     页面: https://www.notion.so/{page_id.replace('-', '')}")
        return page_id
    else:
        print(f"  ❌ Notion推送失败")
        return None

def main():
    print("=" * 60)
    print("推送到Notion - 适配版")
    print("=" * 60)
    
    # 找到所有分析报告
    analysis_files = glob.glob(os.path.join(WORK_DIR, "analysis_*.json"))
    
    if not analysis_files:
        print("❌ 未找到分析报告")
        return
    
    print(f"📋 发现 {len(analysis_files)} 份报告\n")
    
    for i, analysis_path in enumerate(analysis_files, 1):
        try:
            with open(analysis_path, 'r', encoding='utf-8') as f:
                analysis_data = json.load(f)
            
            # 找到对应的meta文件
            meta_path = analysis_data.get('meta_file_path')
            if not meta_path or not os.path.exists(meta_path):
                # 尝试推断meta文件路径
                base_name = os.path.basename(analysis_path).replace("analysis_", "meta_")
                meta_path = os.path.join(os.path.dirname(analysis_path), base_name)
            
            if not os.path.exists(meta_path):
                print(f"⚠️ 找不到Meta文件，跳过: {analysis_path}")
                continue
            
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            print(f"📤 [{i}/{len(analysis_files)}] {meta.get('title', '无标题')[:30]}...")
            push_to_notion(meta, analysis_data)
            
        except Exception as e:
            print(f"❌ 错误: {e}")
        
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("🎉 推送完成！")
    print("=" * 60)

if __name__ == "__main__":
    import time
    main()
