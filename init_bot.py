import os
import lark_oapi as lark
from dotenv import load_dotenv
from lark_oapi.api.drive.v1 import model as drive_v1
from lark_oapi.api.docx.v1 import model as docx_v1

load_dotenv()

client = lark.Client.builder() \
    .app_id(os.getenv("FEISHU_APP_ID")) \
    .app_secret(os.getenv("FEISHU_APP_SECRET")) \
    .build()

def create_bot_home_force():
    print("🤖 正在尝试 '暴力' 建房 (SDK 适配版)...")
    
    try:
        # 👇 核心修正：使用报错提示的 CreateFolderFileRequestBody
        # 注意：不同版本的SDK可能参数位置不同，这里使用最通用的构造方式
        body = drive_v1.CreateFolderFileRequestBody.builder() \
            .name("【Angel】AI视频分析库") \
            .folder_token("") \
            .build()
            
        request = drive_v1.CreateFolderFileReq.builder() \
            .request_body(body) \
            .build()
        
        # 发送请求
        response = client.drive.v1.file.create_folder(request)
        
        if not response.success():
            print(f"❌ 建房失败: {response.code} - {response.msg}")
            print("💡 请检查：应用是否开启 'drive:drive' 权限并发布版本？")
            return

        folder = response.data
        print("\n✅✅✅ 成功了！")
        print(f"📂 文件夹名: {folder.name}")
        print(f"🔗 链接: {folder.url}")
        print("\n👇 【请复制这个 Token 填入主程序】：")
        print(f"🔑 {folder.token}")
        
    except Exception as e:
        # 如果还是报错，我们尝试打印所有可用的属性，帮你 debug
        print(f"❌ 依然报错: {e}")
        print("正在尝试备用方案...")
        try:
             # 备用方案：有时候是 CreateFolderReq
            body = drive_v1.CreateFolderReqBody.builder().name("Angel备用库").folder_token("").build()
            req = drive_v1.CreateFolderReq.builder().request_body(body).build()
            resp = client.drive.v1.folder.create(req)
            if resp.success():
                print(f"✅ 备用方案成功！Token: {resp.data.token}")
        except:
            pass

if __name__ == "__main__":
    create_bot_home_force()
