import os
import subprocess
import sys
import time
from datetime import datetime

# 配置路径
LOG_FILE = "pipeline_debug.log"
FAILED_URLS_FILE = "failed_urls.txt"
URLS_FILE = "urls.txt"

def log_message(message, echo=True):
    """同时打印到屏幕并保存到日志文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    if echo:
        print(formatted_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def run_script(script_name):
    """运行子脚本并实时捕获输出"""
    log_message(f"▶️ 开始执行: {script_name}")
    log_message("-" * 50)
    
    # 使用 subprocess 运行，确保能实时看到输出
    process = subprocess.Popen(
        [sys.executable, script_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8"
    )

    # 实时读取子进程打印的内容并存入日志
    for line in process.stdout:
        print(line, end="") # 屏幕显示
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line) # 日志保存

    process.wait()
    
    if process.returncode == 0:
        log_message(f"✅ {script_name} 执行完毕。")
    else:
        log_message(f"⚠️ {script_name} 运行过程中出现错误 (Exit Code: {process.returncode})")
    
    log_message("-" * 50)
    return process.returncode

def check_failed_downloads():
    """检查日志，提取下载失败的 URL"""
    log_message("🔍 正在扫描下载失败的任务...")
    failed_list = []
    
    # 逻辑：从 pipeline_debug.log 中寻找 "❌ 下载失败" 之前的 "🔗" 链接
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if "❌ 下载失败" in line or "❌ 本次抓取失败" in line:
                    # 向上找最近的链接
                    for j in range(i, i-10, -1):
                        if "🔗" in lines[j]:
                            url = lines[j].split("🔗")[-1].strip()
                            if url not in failed_list:
                                failed_list.append(url)
                            break
    
    if failed_list:
        with open(FAILED_URLS_FILE, "w", encoding="utf-8") as f:
            for url in failed_list:
                f.write(url + "\n")
        log_message(f"🚨 发现 {len(failed_list)} 个下载失败的任务，已记录至: {FAILED_URLS_FILE}")
    else:
        log_message("✨ 本次运行所有下载任务均已成功！")

def main():
    # 初始化日志
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n{'='*25} 新流水线启动 {'='*25}\n")
    
    start_time = time.time()
    log_message("🚀 Angel 的全自动视频分析流水线 启动！")
    
    # 检查工作文件
    if not os.path.exists(URLS_FILE) or os.path.getsize(URLS_FILE) == 0:
        log_message(f"❌ 错误: {URLS_FILE} 为空或不存在，请先放入链接。")
        return

    # 1. 批量下载
    run_script("step3_batch.py")
    
    # 2. 批量分析 (Claude)
    # 因为 Step 2 逻辑里有“跳过已存在报告”，所以即便是重跑也会很智能
    run_script("step2_analyzer.py")
    
    # 3. 批量上传 (Notion)
    run_script("step4_uploader.py")
    
    # 后置处理：检查失败项
    check_failed_downloads()
    
    end_time = time.time()
    duration = round((end_time - start_time) / 60, 2)
    
    log_message(f"🎉 所有动作串联执行完毕！总耗时: {duration} 分钟")
    log_message(f"📝 完整日志请查阅: {LOG_FILE}")
    log_message("============================================================")

if __name__ == "__main__":
    main()
