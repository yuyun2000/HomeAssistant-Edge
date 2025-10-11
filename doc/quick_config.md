# 快速配置指南：运行 HA + ASR + GPT 服务

## 1. 运行 HA（Home Assistant）
> Home Assistant 的安装和运行请参考官方文档，这里不再赘述。

---

## 2. 运行 ASR（语音识别）服务

1. 克隆并进入 ASR 服务项目：
```bash
git clone https://huggingface.co/yunyu1258/AX8850-SenseVoice-server
cd AX8850-SenseVoice-server
```

2. 启动服务（后台运行）：
```bash
nohup uvicorn server:app --host 0.0.0.0 --port 8001 > server.log 2>&1 &
```

3. 说明：
   - 服务会在 **本机 8001 端口** 开启 ASR API。
   - 日志文件保存在 `server.log`。

---

## 3. 运行 HA-GPT 服务

1. 按以下文档安装 **Stackflow**：[安装指南](https://docs.m5stack.com/zh_CN/stackflow/module_llm/software)
2. 确保包含 **llm_llm** 和 **llm_sys** 两个包（部分设备出厂已自带，建议更新到最新版本）。
3. 安装模型：
   ```
   llm-model-qwen2.5-ha-0.5b-ctx-ax650
   ```
4. 模型安装完成后，HA-GPT 服务会自动启动，无需额外配置。

---

## 4. 填写环境配置

1. **获取 HA + ASR + GPT 部署位置的 IP**  
   - 确认三者运行的设备和 IP 地址。
2. **获取 HA 访问令牌（Long-Lived Access Token）**  
   - 在 Home Assistant 用户配置界面生成令牌，步骤参考下图：
     
     ![获取访问令牌](./assets/get_ha_token.png)
3. 编辑 `.env` 文件，填入相关参数

---

## 5. 完成
至此，你已完成 HA + ASR + GPT 服务的快速部署与配置，可以开始使用智能语音交互功能。

