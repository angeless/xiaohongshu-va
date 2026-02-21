import sys

import step5_auto_pipeline


def main():
    print("🚀 使用当前主流水线执行批处理（step3 -> step2 -> step4）")
    step5_auto_pipeline.main()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断执行")
        sys.exit(130)
