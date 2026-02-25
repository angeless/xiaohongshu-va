import os
import time
import threading
from playwright.sync_api import sync_playwright

# 这里定义“浏览器记忆”保存的位置
USER_DATA_DIR = "./browser_memory"
LOGIN_COOKIE_NAMES = {"web_session"}


def _collect_cookie_names(context):
    try:
        cookies = context.cookies("https://www.xiaohongshu.com")
    except Exception:
        try:
            cookies = context.cookies()
        except Exception:
            cookies = []
    return {str(c.get("name", "")).lower() for c in cookies if isinstance(c, dict)}


def is_logged_in(context, page):
    """通过 cookie + 页面特征判断是否已登录。"""
    cookie_names = _collect_cookie_names(context)
    if LOGIN_COOKIE_NAMES.intersection(cookie_names):
        return True

    selectors = [
        '[href*="/user/profile"]',
        'img[class*="avatar"]',
        '.user-side-bar',
        '.user-name',
    ]
    for selector in selectors:
        try:
            if page.query_selector(selector):
                return True
        except Exception:
            continue
    return False


def wait_for_login(context, page, timeout_seconds=300, poll_seconds=2):
    """等待用户登录成功；支持自动检测和手动回车两种结束方式。"""
    manual_confirmed = threading.Event()

    def _wait_manual_input():
        try:
            input(
                "\n✅ 网页已打开！\n"
                "🎉 请在浏览器里扫码登录。\n"
                "👉 可直接按回车手动继续，或等待系统自动检测登录后继续..."
            )
            manual_confirmed.set()
        except EOFError:
            pass

    threading.Thread(target=_wait_manual_input, daemon=True).start()

    deadline = time.time() + timeout_seconds
    last_echo = 0
    while time.time() < deadline:
        if manual_confirmed.is_set():
            return True, "manual"

        if is_logged_in(context, page):
            return True, "auto"

        now = time.time()
        if now - last_echo >= 15:
            remain = max(0, int(deadline - now))
            print(f"⏳ 等待登录完成... (剩余约 {remain} 秒)")
            last_echo = now

        try:
            page.wait_for_timeout(int(poll_seconds * 1000))
        except Exception:
            time.sleep(poll_seconds)

    return False, "timeout"


def login_and_save_state(timeout_seconds=300):
    if not os.path.exists(USER_DATA_DIR):
        os.makedirs(USER_DATA_DIR)
        
    print("🚀 正在启动“有记忆”的浏览器...")
    print("------------------------------------------------")
    print("👉 1. 窗口弹出后，如果页面空白，请手动刷新网页！")
    print("👉 2. 扫码登录。")
    print("👉 3. 登录成功后，回到这里按【回车键】保存退出。")
    print("------------------------------------------------")
    
    with sync_playwright() as p:
        # 启动持久化浏览器
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False, # 必须有界面
            viewport={'width': 1280, 'height': 800},
            channel="chrome", 
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )

        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()
        
        print("⏳ 正在前往小红书首页 (已设置永不超时)...")
        try:
            # 使用有限超时，避免网络异常导致永久阻塞
            page.goto("https://www.xiaohongshu.com", timeout=45000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"⚠️ 页面加载提示: {e}")
            print("   (这不影响使用，只要你能看到网页就行)")

        success, mode = wait_for_login(context, page, timeout_seconds=timeout_seconds)
        if success and mode == "auto":
            print("✅ 检测到登录成功，准备保存并返回流程。")
        elif success and mode == "manual":
            print("✅ 已手动确认，准备保存并返回流程。")
        else:
            print("⚠️ 登录等待超时：将保存当前状态并退出。")

        # 给一点时间让 cookie 写入硬盘
        print("💾 正在保存记忆...")
        page.wait_for_timeout(3000)
        
        try:
            context.storage_state(path=os.path.join(USER_DATA_DIR, "state.json"))
        except Exception:
            pass

        context.close()
        print(f"✅ 成功！登录状态已保存到: {USER_DATA_DIR}")
        print("   现在可继续运行 step3_batch.py / step5_auto_pipeline.py 开始分析。")

if __name__ == "__main__":
    login_and_save_state()
