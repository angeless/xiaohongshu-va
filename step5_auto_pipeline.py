import os
import argparse
import subprocess
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 配置路径
LOG_FILE = os.path.join(BASE_DIR, "pipeline_debug.log")
FAILED_URLS_FILE = os.path.join(BASE_DIR, "failed_urls.txt")
URLS_FILE = os.path.join(BASE_DIR, "urls.txt")

def log_message(message, echo=True):
    """同时打印到屏幕并保存到日志文件"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_msg = f"[{timestamp}] {message}"
    if echo:
        print(formatted_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(formatted_msg + "\n")

def run_script(script_name, extra_args=None):
    """运行子脚本并实时捕获输出"""
    log_message(f"▶️ 开始执行: {script_name}")
    log_message("-" * 50)

    cmd = [sys.executable, script_name]
    if extra_args:
        cmd.extend(extra_args)

    # 使用 subprocess 运行，确保能实时看到输出
    process = subprocess.Popen(
        cmd,
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

def extract_failed_urls_from_lines(lines, lookback=10):
    """从日志行中提取下载失败对应的 URL。"""
    failed_list = []
    for i, line in enumerate(lines):
        if "❌ 下载失败" in line or "❌ 本次抓取失败" in line:
            start_idx = max(0, i - lookback)
            for j in range(i, start_idx - 1, -1):
                if "🔗" in lines[j]:
                    url = lines[j].split("🔗")[-1].strip()
                    if url and url not in failed_list:
                        failed_list.append(url)
                    break
    return failed_list

def check_failed_downloads():
    """检查日志，提取下载失败的 URL"""
    log_message("🔍 正在扫描下载失败的任务...")

    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        failed_list = extract_failed_urls_from_lines(lines)
    else:
        failed_list = []

    if failed_list:
        with open(FAILED_URLS_FILE, "w", encoding="utf-8") as f:
            for url in failed_list:
                f.write(url + "\n")
        log_message(f"🚨 发现 {len(failed_list)} 个下载失败的任务，已记录至: {FAILED_URLS_FILE}")
    else:
        log_message("✨ 本次运行所有下载任务均已成功！")

def main(cli_args=None):
    parser = argparse.ArgumentParser(
        description="Step 5: 全自动流水线（下载 → 分析 → 上传 Notion）"
    )
    parser.add_argument(
        "--urls-file", type=str, default=URLS_FILE,
        help=f"链接文件路径（默认: {URLS_FILE}）"
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="分析完成后自动删除视频文件以释放磁盘空间"
    )
    parser.add_argument(
        "--skip-upload", action="store_true",
        help="跳过 Step 4 Notion 上传"
    )
    args = parser.parse_args(cli_args)

    os.chdir(BASE_DIR)

    # 初始化日志
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n{'='*25} 新流水线启动 {'='*25}\n")

    start_time = time.time()
    log_message("🚀 全自动视频分析流水线 启动！")

    # 检查工作文件
    urls_file = args.urls_file
    if not os.path.exists(urls_file) or os.path.getsize(urls_file) == 0:
        log_message(f"❌ 错误: {urls_file} 为空或不存在，请先放入链接。")
        return

    # 1. 批量下载
    batch_args = ["--urls-file", urls_file]
    run_script(os.path.join(BASE_DIR, "step3_batch.py"), extra_args=batch_args)

    # 2. 批量分析
    analyzer_args = []
    if args.cleanup:
        analyzer_args.append("--cleanup")
    run_script(os.path.join(BASE_DIR, "step2_analyzer.py"), extra_args=analyzer_args or None)

    # 3. 批量上传 (Notion)
    if not args.skip_upload:
        run_script(os.path.join(BASE_DIR, "step4_uploader.py"))
    else:
        log_message("⏭️ 已跳过 Notion 上传（--skip-upload）")

    # 后置处理：检查失败项
    check_failed_downloads()

    end_time = time.time()
    duration = round((end_time - start_time) / 60, 2)

    log_message(f"🎉 所有动作串联执行完毕！总耗时: {duration} 分钟")
    log_message(f"📝 完整日志请查阅: {LOG_FILE}")
    log_message("============================================================")

if __name__ == "__main__":
    main()
