import os
import time
from playwright.sync_api import sync_playwright

# 这里定义“浏览器记忆”保存的位置
USER_DATA_DIR = "./browser_memory"

def login_and_save_state():
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
        
        page = context.pages[0]
        
        print("⏳ 正在前往小红书首页 (已设置永不超时)...")
        try:
            # 修改点：timeout=0 (无限等待)，wait_until='domcontentloaded' (只要骨架加载完就行)
            page.goto("https://www.xiaohongshu.com", timeout=0, wait_until="domcontentloaded")
        except Exception as e:
            print(f"⚠️ 页面加载提示: {e}")
            print("   (这不影响使用，只要你能看到网页就行)")

        # 这里的 input 是为了卡住程序，等你操作
        input("\n✅ 网页已打开！\n🎉 请在浏览器里扫码登录，登录成功并刷新一下页面后...\n👉 按 【回车键 (Enter)】 结束程序...")

        # 给一点时间让 cookie 写入硬盘
        print("💾 正在保存记忆...")
        page.wait_for_timeout(3000)
        
        context.close()
        print(f"✅ 成功！登录状态已保存到: {USER_DATA_DIR}")
        print("   现在你可以运行 step1_crawler.py 了！")

if __name__ == "__main__":
    login_and_save_state()
