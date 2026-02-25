import os
import sys
import json
import time
import re
import random
import subprocess
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin
from datetime import datetime
from playwright.sync_api import sync_playwright

# 确保工作目录存在
WORK_DIR = "workspace_data"
os.makedirs(WORK_DIR, exist_ok=True)
USER_DATA_DIR = "./browser_memory"

LOGIN_PAGE_SELECTORS = [
    '.login-container',
    '.login-mask',
    'input[placeholder*="手机号"]',
    'input[placeholder*="验证码"]',
]

LOGIN_HINT_WORDS = [
    "扫码登录",
    "登录后",
    "请先登录",
    "手机号登录",
    "验证码登录",
]

PROFILE_URL_HINTS = ["/user/profile/", "www.xiaohongshu.com/user/"]
LOGIN_COOKIE_PREFIXES = ("web_session",)
DEFAULT_LOGIN_WAIT_SECONDS = int(os.getenv("LOGIN_WAIT_SECONDS", "300"))
STRICT_LOGIN_REQUIRED = os.getenv("STRICT_LOGIN_REQUIRED", "1") != "0"
LOGIN_SUCCESS_SELECTORS = [
    '[href*="/user/profile"]',
    '.user-side-bar',
    '.author-wrapper',
]

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


def download_video_with_ytdlp(note_url, timestamp):
    """兜底下载：直接使用 yt-dlp 下载笔记视频。"""
    template = os.path.join(WORK_DIR, f"video_{timestamp}.%(ext)s")
    cmd = [
        "yt-dlp",
        "-f",
        "bv*[height<=1080]+ba/b[height<=1080]/b",
        "--merge-output-format",
        "mp4",
        "-o",
        template,
        note_url,
    ]
    try:
        print(f"🛟 [Fallback] 使用 yt-dlp 兜底下载: {note_url[:80]}...")
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "").strip()
            print(f"⚠️ yt-dlp 兜底下载失败: {msg[:300]}")
            return None
        # 优先 mp4，其次匹配同前缀文件
        mp4_path = os.path.join(WORK_DIR, f"video_{timestamp}.mp4")
        if os.path.exists(mp4_path):
            return mp4_path
        prefix = os.path.join(WORK_DIR, f"video_{timestamp}.")
        candidates = [
            os.path.join(WORK_DIR, f)
            for f in os.listdir(WORK_DIR)
            if f.startswith(f"video_{timestamp}.")
        ]
        return candidates[0] if candidates else None
    except Exception as e:
        print(f"⚠️ yt-dlp 兜底下载异常: {e}")
        return None

def _has_login_cookie(context):
    if not context:
        return False
    try:
        cookies = context.cookies("https://www.xiaohongshu.com")
    except Exception:
        try:
            cookies = context.cookies()
        except Exception:
            cookies = []
    names = {str(c.get("name", "")).lower() for c in cookies if isinstance(c, dict)}
    return any(any(name.startswith(prefix) for prefix in LOGIN_COOKIE_PREFIXES) for name in names)


def _has_note_content(page):
    try:
        if page.query_selector("video"):
            return True
    except Exception:
        pass
    try:
        if page.query_selector("#detail-desc"):
            return True
    except Exception:
        pass
    return False


def _has_login_success_marker(page):
    for selector in LOGIN_SUCCESS_SELECTORS:
        try:
            if page.query_selector(selector):
                return True
        except Exception:
            continue
    return False


def page_requires_login(page, context=None):
    """判断页面是否处于登录态缺失场景。"""
    try:
        if page.is_closed():
            return False
    except Exception:
        return False

    signal_score = 0
    try:
        url = (page.url or "").lower()
        if "/login" in url:
            signal_score += 2
    except Exception:
        pass

    has_login_selector = False
    for selector in LOGIN_PAGE_SELECTORS:
        try:
            if page.query_selector(selector):
                has_login_selector = True
                break
        except Exception:
            continue

    has_login_hint = False
    try:
        content = page.content()
        if any(word in content for word in LOGIN_HINT_WORDS):
            has_login_hint = True
    except Exception:
        pass

    if has_login_selector:
        signal_score += 1
    if has_login_hint:
        signal_score += 1
    if signal_score >= 2 and not _has_login_success_marker(page):
        return True

    # 既没有明确登录页信号，又有登录成功/内容信号时，不视为需要登录
    if _has_login_success_marker(page) or _has_note_content(page):
        return False

    # 无明显信号时交给严格模式策略（在 wait_for_login_if_needed 里处理）
    return False


def wait_for_login_if_needed(page, context=None, timeout_seconds=None, poll_seconds=2, force_wait=False):
    """若检测到登录页面，则等待用户登录完成后继续。"""
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_LOGIN_WAIT_SECONDS

    try:
        if page.is_closed():
            print("⚠️ 页面已关闭，跳过登录等待。")
            return False
    except Exception:
        return False

    has_cookie = _has_login_cookie(context)
    requires_login = page_requires_login(page, context=context)

    # 默认严格模式：没有登录态就先等待，避免页面刚开就关闭，用户来不及扫码。
    if force_wait:
        print(
            f"🔐 将强制等待登录（最多 {timeout_seconds} 秒），请扫码完成后继续..."
        )
    elif not has_cookie and STRICT_LOGIN_REQUIRED:
        print(
            f"🔐 未检测到登录态（web_session），将等待最多 {timeout_seconds} 秒供你扫码登录..."
        )
    elif not requires_login:
        return True
    else:
        print("🔐 检测到需要登录，请在浏览器中扫码完成登录，脚本将自动继续...")

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            if page.is_closed():
                print("⚠️ 页面已关闭，结束登录等待。")
                return False
        except Exception:
            return False

        has_cookie = _has_login_cookie(context)
        requires_login = page_requires_login(page, context=context)

        # 严格模式下，优先等到可用登录态；非严格模式按页面状态放行。
        if has_cookie and (not requires_login or _has_note_content(page) or _has_login_success_marker(page)):
            print("✅ 检测到登录完成，继续执行抓取。")
            try:
                page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            return True

        if not force_wait and not STRICT_LOGIN_REQUIRED and not requires_login:
            return True

        try:
            page.wait_for_timeout(int(poll_seconds * 1000))
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断登录等待。")
            return False
        except Exception:
            try:
                if page.is_closed():
                    print("⚠️ 页面/浏览器已关闭，结束登录等待。")
                    return False
            except Exception:
                return False
            time.sleep(poll_seconds)

    if STRICT_LOGIN_REQUIRED and not _has_login_cookie(context):
        print("⚠️ 登录等待超时，仍未检测到登录态。")
    else:
        print("⚠️ 登录等待超时，继续尝试抓取（可能失败）。")
    return False


def is_profile_url(url):
    if not url:
        return False
    u = str(url).lower()
    return any(hint in u for hint in PROFILE_URL_HINTS) and "/explore/" not in u


def _extract_note_id(url):
    if not url:
        return "unknown"
    match = re.search(r"/explore/(\w+)", url)
    return match.group(1) if match else "unknown"


def _extract_stats_from_page(page):
    stats = {'likes': '0', 'collects': '0', 'comments': '0'}
    try:
        counts = page.query_selector_all(".interact-container .count")
        if len(counts) >= 3:
            stats['likes'] = counts[0].inner_text()
            stats['collects'] = counts[1].inner_text()
            stats['comments'] = counts[2].inner_text()
        else:
            content = page.content()
            likes_match = re.search(r'(?:点赞|赞)\s*([\d\.w万k]+)', content)
            collects_match = re.search(r'(?:收藏|藏)\s*([\d\.w万k]+)', content)
            comments_match = re.search(r'(?:评论|评)\s*([\d\.w万k]+)', content)
            if likes_match:
                stats['likes'] = likes_match.group(1)
            if collects_match:
                stats['collects'] = collects_match.group(1)
            if comments_match:
                stats['comments'] = comments_match.group(1)
    except Exception as e:
        print(f"⚠️ 抓取互动数据微瑕: {e}")
    return stats


def _resolve_video_url(page, sniffed_url=None):
    final_download_url = sniffed_url
    if not final_download_url:
        try:
            content = page.content()
            matches = re.findall(r'"masterUrl":"(http[^"]+)"', content)
            if matches:
                final_download_url = matches[0].encode('utf-8').decode('unicode_escape')
                print(f"🔍 源码提取成功: {final_download_url[:40]}...")
            if not final_download_url:
                # 兜底提取页面中直出的 mp4 资源
                mp4_matches = re.findall(r'(https?://[^"\\]+?\.mp4[^"\\]*)', content)
                if mp4_matches:
                    final_download_url = mp4_matches[0]
                    print(f"🔍 源码兜底提取 mp4 成功: {final_download_url[:40]}...")
        except Exception as e:
            print(f"⚠️ 源码提取失败: {e}")
    if not final_download_url:
        try:
            video_element = page.query_selector('video')
            if video_element:
                src = video_element.get_attribute("src")
                if src and not src.startswith("blob:"):
                    final_download_url = src
        except Exception:
            pass
    return final_download_url


def _extract_note_meta(page, source_url, sniffed_video_url=None):
    note_url = page.url if page.url else source_url
    note_id = _extract_note_id(note_url)
    timestamp = int(datetime.now().timestamp() * 1000)

    print("⏳ 缓冲 3 秒以确保互动数据加载...")
    time.sleep(3)
    try:
        page.mouse.wheel(0, 500)
    except Exception:
        pass
    time.sleep(1)

    stats = _extract_stats_from_page(page)
    print(f"📊 抓取到数据：赞({stats['likes']}) 藏({stats['collects']}) 评({stats['comments']})")

    final_download_url = _resolve_video_url(page, sniffed_video_url)
    if not final_download_url:
        raise Exception("❌ 未能找到有效的视频地址")

    title = page.title()
    desc = ""
    try:
        desc_element = page.query_selector("#detail-desc")
        if desc_element:
            desc = desc_element.inner_text()
    except Exception:
        pass

    author = "Unknown"
    try:
        author_elem = page.query_selector(".username")
        if author_elem:
            author = author_elem.inner_text().strip()
    except Exception:
        pass
    author = author.replace("关注", "").strip()

    comments_list = []
    try:
        comment_elements = page.query_selector_all(".comment-item .content")
        for el in comment_elements[:5]:
            comments_list.append(el.inner_text())
    except Exception:
        pass

    cover_url = ""
    try:
        meta_img = page.query_selector('meta[property="og:image"]')
        if meta_img:
            cover_url = meta_img.get_attribute("content")
    except Exception:
        pass

    video_filename = f"video_{timestamp}.mp4"
    local_video_path = None
    if final_download_url:
        print(f"📥 [Video] 准备下载...")
        local_video_path = download_video(final_download_url, video_filename)

    # 页面提流失败时，使用 yt-dlp 兜底
    if not local_video_path:
        local_video_path = download_video_with_ytdlp(note_url or source_url, timestamp)

    if not local_video_path:
        raise Exception("❌ 未能找到有效的视频地址")

    meta_data = {
        "id": note_id,
        "url": note_url or source_url,
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
    print(f"✅ 元数据保存完成: {json_filename}")
    return json_path


def _collect_note_links(page):
    links = []
    try:
        anchors = page.query_selector_all('a[href*="/explore/"]')
        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue
            full = urljoin("https://www.xiaohongshu.com", href)
            if "/explore/" in full:
                links.append(full)
    except Exception:
        pass
    # 保序去重
    seen = set()
    uniq = []
    for u in links:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq


def _click_note_card(page, note_url):
    """优先模拟真实点击卡片进入详情页。"""
    try:
        anchors = page.query_selector_all('a[href*="/explore/"]')
        for a in anchors:
            href = a.get_attribute("href")
            if not href:
                continue
            full = urljoin("https://www.xiaohongshu.com", href)
            if full != note_url:
                continue
            try:
                a.scroll_into_view_if_needed(timeout=3000)
            except Exception:
                pass
            a.click(timeout=6000)
            return True
    except Exception:
        pass
    return False

def run_scraper(url):
    print(f"🚀 [Step 1] 启动猎人模式: {url}")

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
                except Exception:
                    pass

            page.on("response", handle_response)
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")

            try:
                print("🌍 正在加载页面 (设置30秒超时)...")
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print(f"⚠️ 页面加载提示 (Timeout)，正在停止网页转圈以提取数据...")
                try:
                    page.evaluate("window.stop()")
                except Exception:
                    pass

            wait_for_login_if_needed(page, context=context)
            json_path = _extract_note_meta(page, url, real_video_url["url"])
            print("✅ [Step 1 完成] 数据已保存")
            time.sleep(1)
            return json_path
        finally:
            if context:
                try:
                    context.close()
                except:
                    pass


def run_profile_scraper(profile_url, max_items=10):
    """达人主页真实用户模式：点击卡片 -> 分析 -> 返回 -> 下一条。"""
    print(f"🚀 [Step 1] 达人主页模式: {profile_url}")
    print(f"🎯 目标采集条数: {max_items}")

    with sync_playwright() as p:
        context = None
        results = []
        visited = set()
        try:
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    headless=False,
                    viewport={'width': 1280, 'height': 800},
                    channel="chrome",
                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    headless=False,
                    viewport={'width': 1280, 'height': 800},
                    args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
                )

            page = context.pages[0] if context.pages else context.new_page()
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined })")

            print("🌍 打开达人主页...")
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            wait_for_login_if_needed(page, context=context)
            time.sleep(2)

            idle_rounds = 0
            while len(results) < max_items and idle_rounds < 8:
                note_links = _collect_note_links(page)
                pending = [u for u in note_links if u not in visited]

                if not pending:
                    idle_rounds += 1
                    print("↘️ 未发现新卡片，向下滚动加载更多...")
                    try:
                        page.mouse.wheel(0, 1800)
                    except Exception:
                        pass
                    time.sleep(2)
                    continue

                idle_rounds = 0
                for note_url in pending:
                    if len(results) >= max_items:
                        break
                    visited.add(note_url)
                    print(f"\n🎬 进入笔记 ({len(results)+1}/{max_items}): {note_url}")

                    sniffed = {"url": None}

                    def handle_response(response):
                        try:
                            if "video/mp4" in response.headers.get("content-type", "") or ".mp4" in response.url:
                                if "sns-video" in response.url or "spectrum" in response.url:
                                    if not sniffed["url"]:
                                        sniffed["url"] = response.url
                        except Exception:
                            pass

                    page.on("response", handle_response)
                    try:
                        clicked = _click_note_card(page, note_url)
                        if clicked:
                            print("🖱️ 已模拟点击卡片进入详情页。")
                            time.sleep(2)
                        else:
                            print("⚠️ 卡片点击失败，降级为同会话直达详情页。")
                            try:
                                page.goto(note_url, wait_until="domcontentloaded", timeout=30000)
                            except Exception:
                                page.goto(note_url, wait_until="load", timeout=45000)

                        wait_for_login_if_needed(page, context=context)
                        json_path = _extract_note_meta(page, note_url, sniffed["url"])
                        results.append(json_path)
                        print(f"✅ 当前笔记采集完成: {os.path.basename(json_path)}")
                    except Exception as e:
                        print(f"❌ 当前笔记采集失败: {e}")
                    finally:
                        try:
                            page.remove_listener("response", handle_response)
                        except Exception:
                            pass

                    # 模拟真实用户返回达人主页
                    try:
                        page.go_back(wait_until="domcontentloaded", timeout=15000)
                    except Exception:
                        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(1.0, 2.2))

            print(f"\n🎉 达人主页采集结束，成功 {len(results)} 条。")
            return results
        finally:
            if context:
                try:
                    context.close()
                except Exception:
                    pass
