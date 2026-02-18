import os
from dotenv import load_dotenv
import lark_oapi as lark
from lark_oapi.api.docx.v1 import *

load_dotenv()

# 你的文件夹 Token
FOLDER_TOKEN = "XfeKfztHglyXk1dtyO1cFM2Xnye"

client = lark.Client.builder() \
    .app_id(os.getenv("FEISHU_APP_ID")) \
    .app_secret(os.getenv("FEISHU_APP_SECRET")) \
    .build()

def test_create():
    print("🧪 正在测试飞书文档创建权限...")
    try:
        request = CreateDocumentRequest.builder() \
            .request_body(Document.builder()
                .title("【测试】机器人权限测试文档")
                .folder_token(FOLDER_TOKEN)
                .build()) \
            .build()
        
        response = client.docx.v1.document.create(request)
        
        if response.success():
            print(f"✅ 成功！文档已创建，ID: {response.data.document.document_id}")
            print("👉 快去你的飞书文件夹看看有没有这个文档！")
        else:
            print(f"❌ 失败！错误码: {response.code}")
            print(f"❌ 错误信息: {response.msg}")
            print("💡 解决办法：请去飞书文件夹，点右上角'...' -> '添加协作者' -> 搜索你的机器人名字 -> 给它'可编辑'权限。")
            
    except Exception as e:
        print(f"❌ 代码报错: {e}")

if __name__ == "__main__":
    test_create()
