import os
import sys
import time

# --- 核心修复：强制引用当前目录 ---
# 这句代码能保证 Python 一定能在当前文件夹下找到 my_research_bot
sys.path.append(os.getcwd())

def main():
    print("🚀 正在连接 Angel 的 AI 大脑...")

    # 1. 尝试导入机器人
    try:
        import my_research_bot
        print("✅ 成功导入 my_research_bot！")
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("💡 请检查 my_research_bot.py 里面是否有语法错误？(比如少个括号)")
        return
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
        return

    # 2. 检查链接文件
    txt_file = "links.txt"
    if not os.path.exists(txt_file):
        print(f"❌ 找不到 {txt_file}！请创建一个 txt 文件，把小红书链接一行一个贴进去。")
        return

    # 3. 读取链接
    with open(txt_file, "r", encoding="utf-8") as f:
        # 过滤掉空行和非链接行
        links = [line.strip() for line in f if line.strip() and "http" in line]

    if not links:
        print("⚠️ links.txt 里没有有效的链接，任务结束。")
        return

    print(f"\n📋 发现 {len(links)} 个待处理任务\n" + "="*40)

    # 4. 开始循环处理
    for i, url in enumerate(links):
        print(f"\n🎬 [任务 {i+1}/{len(links)}] 正在处理...")
        print(f"🔗 链接: {url}")
        
        try:
            # 核心调用：直接把 URL 传给机器人
            my_research_bot.process_single_link(url)
            
            # 这里的延时是为了防止请求太快被 Notion 或 小红书 限制
            if i < len(links) - 1:
                print("☕️ 任务完成，休息 5 秒继续下一个...")
                time.sleep(5)
            
        except Exception as e:
            print(f"⚠️ 当前链接处理出错: {e}")
            import traceback
            traceback.print_exc()
            continue
            
        print("-" * 40)

    print(f"\n🎉🎉🎉 所有任务全部执行完毕！快去 Notion 看看战果吧！")

if __name__ == "__main__":
    main()
