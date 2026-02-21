import os
import sys
import json
import time
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from playwright.sync_api import sync_playwright

# 确保工作目录存在
WORK_DIR = "workspace_data"
os.makedirs(WORK_DIR, exist_ok=True)
USER_DATA_DIR = "./browser_memory"

def get_robust_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def download_video(url, filename):
    if not url or url.startswith("blob:"):
        print(f"❌ 无法下载，URL无效或为Blob: {url}")
        return None
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.xiaohongshu.com/"
        }
        print(f"📥 正在请求视频流 (含重试机制): {url[:50]}...")
        
        session = get_robust_session()
        response = session.get(url, headers=headers, stream=True, timeout=120)
        
        if response.status_code == 200:
            save_path = os.path.join(WORK_DIR, filename)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            
            if os.path.getsize(save_path) < 1024:
                print("⚠️ 下载文件过小，可能已损坏")
                return None
                
            print(f"✅ 视频下载完成: {save_path}")
            return save_path
        else:
            print(f"⚠️ 下载失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"⚠️ 下载流出错: {e}")
    return None

def run_scraper(url):
    print(f"🚀 [Step 1] 启动猎人模式: {url}")
    
    note_id = "unknown"
    match = re.search(r'/explore/(\w+)', url)
    if match:
        note_id = match.group(1)
    
    timestamp = int(datetime.now().timestamp())
    
    with sync_playwright() as p:
        context = None
        if not os.path.exists(USER_DATA_DIR):
             print(f"⚠️ 警告：未找到浏览器记忆文件夹，请先运行 login_tool.py！")

        print(f"👀 正在唤醒有记忆的浏览器...")
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                viewport={'width': 1280, 'height': 800},
                channel="chrome", 
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
        except:
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                viewport={'width': 1280, 'height': 800},
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )

        try:
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = context.new_page()
            
            real_video_url = {"url": None}
            
            def handle_response(response):
                try:
                    if "video/mp4" in response.headers.get("content-type", "") or ".mp4" in response.url:
                        if "sns-video" in response.url or "spectrum" in response.url:
                            if not real_video_url["url"]: 
                                print(f"🕵️ 嗅探到真实视频流: {response.url[:40]}...")
                                real_video_url["url"] = response.url
                except: pass

            page.on("response", handle_response)
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")

            try:
                print("🌍 正在加载页面 (设置30秒超时)...")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"⚠️ 页面加载提示 (Timeout)，正在停止网页转圈以提取数据...")
                try:
                    page.evaluate("window.stop()")
                except: pass

            print("⏳ 缓冲 5 秒以确保互动数据加载...")
            time.sleep(5)
            
            try:
                page.mouse.wheel(0, 500)
            except: pass
            time.sleep(2)
            
            # --- 数据抓取升级：赞藏评核心提取 ---
            stats = {'likes': '0', 'collects': '0', 'comments': '0'}
            try:
                # 1. 尝试直接获取选择器中的计数
                # 小红书PC端互动的常见类名是 .count 或 .interact-container 中的特定 span
                counts = page.query_selector_all(".interact-container .count")
                if len(counts) >= 3:
                    stats['likes'] = counts[0].inner_text()
                    stats['collects'] = counts[1].inner_text()
                    stats['comments'] = counts[2].inner_text()
                else:
                    # 2. 正则兜底逻辑
                    content = page.content()
                    # 匹配：赞 1.2万 或 点赞 1234
                    likes_match = re.search(r'(?:点赞|赞)\s*([\d\.w万k]+)', content)
                    collects_match = re.search(r'(?:收藏|藏)\s*([\d\.w万k]+)', content)
                    comments_match = re.search(r'(?:评论|评)\s*([\d\.w万k]+)', content)
                    
                    if likes_match: stats['likes'] = likes_match.group(1)
                    if collects_match: stats['collects'] = collects_match.group(1)
                    if comments_match: stats['comments'] = comments_match.group(1)
                
                print(f"📊 抓取到数据：赞({stats['likes']}) 藏({stats['collects']}) 评({stats['comments']})")
            except Exception as e:
                print(f"⚠️ 抓取互动数据微瑕: {e}")

            final_download_url = real_video_url["url"]

            if not final_download_url:
                print("⚠️ 未监听到网络流，尝试从源码提取...")
                try:
                    content = page.content()
                    matches = re.findall(r'"masterUrl":"(http[^"]+)"', content)
                    if matches:
                        final_download_url = matches[0].encode('utf-8').decode('unicode_escape')
                        print(f"🔍 源码提取成功: {final_download_url[:40]}...")
                except Exception as e:
                    print(f"⚠️ 源码提取失败: {e}")

            if not final_download_url:
                print("⚠️ 源码提取也失败，尝试获取标签 src...")
                try:
                    video_element = page.query_selector('video')
                    if video_element:
                        src = video_element.get_attribute("src")
                        if src and not src.startswith("blob:"):
                            final_download_url = src
                except: pass

            if not final_download_url:
                raise Exception("❌ 未能找到有效的视频地址")

            # --- 其他元数据 ---
            title = page.title()
            desc = ""
            try:
                desc_element = page.query_selector("#detail-desc")
                if desc_element: desc = desc_element.inner_text()
            except: pass
            
            author = "Unknown"
            try:
                author_elem = page.query_selector(".username")
                if author_elem: author = author_elem.inner_text().strip()
            except: pass

            author = author.replace("关注", "").strip()

            comments_list = []
            try:
                comment_elements = page.query_selector_all(".comment-item .content")
                for el in comment_elements[:5]: 
                    comments_list.append(el.inner_text())
            except: pass
            
            cover_url = ""
            try:
                meta_img = page.query_selector('meta[property="og:image"]')
                if meta_img: cover_url = meta_img.get_attribute("content")
            except: pass

            video_filename = f"video_{timestamp}.mp4"
            print(f"📥 [Video] 准备下载...")
            local_video_path = download_video(final_download_url, video_filename)
            
            if not local_video_path:
                raise Exception("视频下载最终失败")

            meta_data = {
                "id": note_id,
                "url": url,
                "title": title,
                "author": author,
                "desc": desc,
                "stats": stats,
                "top_comments": "\n".join(comments_list),
                "cover_url": cover_url,
                "local_video_path": local_video_path,
                "timestamp": timestamp
            }
            
            json_filename = f"meta_{timestamp}.json"
            json_path = os.path.join(WORK_DIR, json_filename)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=2)
                
            print("✅ [Step 1 完成] 数据已保存")
            time.sleep(1)
            return json_path
        finally:
            if context:
                try:
                    context.close()
                except:
                    pass
