import sys
import time
import random
import os
import json
import step1_scraper as step1

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def main():
    os.chdir(BASE_DIR)
    print("🚀 启动 [Step 1: 批量下载] 模式...")
    print("👉 本步骤只负责将视频和元数据保存到本地，不进行分析。")
    print(f"📁 工作目录: {BASE_DIR}")
    print(f"📄 读取链接文件: {os.path.join(BASE_DIR, 'urls.txt')}")
    print("="*60)
    
    links_file = os.path.join(BASE_DIR, "urls.txt")
    links = []
    
    # 读取链接
    if os.path.exists(links_file):
        with open(links_file, "r", encoding="utf-8") as f:
            links = [line.strip() for line in f if line.strip()]
            
    if not links:
        print(f"⚠️ 未找到 {links_file} 或文件为空。")
        print("👉 请直接粘贴链接 (输入 'run' 开始):")
        while True:
            line = input("> ").strip()
            if line == 'run': break
            if line: links.append(line)
            
    print(f"📋 任务队列: {len(links)} 个")
    print("="*60)
    
    success_count = 0
    
    for i, url in enumerate(links):
        print(f"\n🎬 [任务 {i+1}/{len(links)}] 下载中...")
        print(f"🔗 {url}")
        
        try:
            if step1.is_profile_url(url):
                max_items = int(os.getenv("PROFILE_MAX_ITEMS", "10"))
                print(f"👤 检测到达人主页链接，切换真实点击模式（最多 {max_items} 条）")
                json_list = step1.run_profile_scraper(url, max_items=max_items)
                if json_list:
                    print(f"✅ 达人主页采集成功: {len(json_list)} 条")
                    success_count += len(json_list)
                else:
                    print(f"❌ 达人主页采集失败")
            else:
                # 调用单条爬虫
                json_path = step1.run_scraper(url)
                if json_path:
                    print(f"✅ 下载成功: {os.path.basename(json_path)}")
                    success_count += 1
                else:
                    print(f"❌ 下载失败")
                
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断任务，停止批处理。")
            break
        except Exception as e:
            print(f"❌ 异常: {e}")
            
        # 随机休息，防封号
        if i < len(links) - 1:
            t = random.randint(5, 12)
            print(f"☕️ 休息 {t} 秒...")
            time.sleep(t)

    print("\n" + "="*60)
    print(f"🎉 下载阶段结束！成功: {success_count}/{len(links)}")
    print("👉 请继续运行: python3 step2_analyzer.py 进行本地分析")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行。")
