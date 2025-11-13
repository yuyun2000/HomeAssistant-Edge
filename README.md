# 🏠 HomeAssistant Edge
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)]()
[![Platform](https://img.shields.io/badge/platform-AX650-orange)]()
**HomeAssistant Edge** 是一个基于 **AX650 本地 AI 芯片** 的离线语音控制系统，集成 **离线语音识别 (ASR)** 与 **本地大语言模型 (LLM)**，无需云服务，响应极快并完全保护隐私。

---

## ✨ 功能特点
- 🔌 **完全离线**：ASR 和 LLM 均运行于 AX650 本地
- 🗣 **语音控制**：可通过语音操作 Home Assistant 中的各种智能家居设备
- ⚡ **毫秒级响应**：本地处理，无需等待云端
- 🌐 **高度可扩展**：通过 `devices.yaml` 快速适配新设备
- 🔒 **隐私安全**：所有音频与数据均在本地处理
- 💬 **多语言支持（中英双语）**：当前支持 **中文和英文语音命令**，英文命令的响应更精准

> 当前版本已支持 **一句话控制多个设备**（如“打开客厅和厨房的灯”），但暂不支持类似 **“打开所有的灯”** 这类全局指令。
> 下一阶段将持续优化以下功能：
> - 🕒 **定时器功能**（例如“5分钟后关闭空调”）  
> - 🧩 **隐含指令增强**（对模糊指令的识别和上下文理解）  
> - 🈶 **中文与日文语音指令优化**  
> - 🗄️ **单语句多条命令的执行能力提升（目标：最多支持4条命令）**

---

## 📋 当前支持设备与服务
| 设备类型 | 可用操作（service） |
|----------|--------------------|
| **灯光 (`light`)** | `turn_on`（可调颜色/亮度）、`turn_off`、`toggle` |
| **窗帘/百叶窗 (`blinds` / `cover`)** | `open_cover`、`close_cover`、`stop_cover`、`toggle` |
| **风扇 (`fan`)** | `turn_on`、`turn_off`、`toggle`、`increase_speed`、`decrease_speed` |
| **车库门 (`garage_door`)** | `open_cover`、`close_cover`、`stop_cover`、`toggle` |
| **恒温器/空调 (`climate`)** | `set_temperature`、`set_humidity`、`set_fan_mode`、`set_hvac_mode` |
| **门锁 (`lock`)** | `lock`、`unlock` |
| **媒体播放器 (`media_player`)** | `turn_on`、`turn_off`、`toggle`、`volume_up`、`volume_down`、`volume_mute`、`media_play`、`media_pause`、`media_stop`、`media_play_pause`、`media_next_track`、`media_previous_track` |
| **开关 (`switch`)** | `turn_on`、`turn_off`、`toggle` |

---

## 🚀 系统架构
```mermaid
flowchart LR
    MIC[🎙 麦克风输入] --> ASR[🗣 离线语音识别 - AX650]
    ASR --> TEXT[📝 识别文本]
    TEXT --> LLM[🧠 本地大语言模型 - AX650]
    LLM --> CMD[🔧 生成 Home Assistant 控制指令]
    CMD --> HA[🏠 Home Assistant API]
    HA --> DEVICE[💡 智能家居设备]
```

---

## 📦 安装与部署

📖 **快速启动（推荐）**  
如果你想快速完成 HA + ASR + 本地 LLM 的离线部署，请参考：  
[📄 Quick Config 指南](./doc/quick_config.md)  
该文档包括：
- 离线 ASR 服务启动
- LLM 模型安装及运行
- Home Assistant 接口配置（IP、令牌等）

---

### 1️⃣ 克隆仓库
```bash
git clone https://github.com/yuyun2000/HomeAssistant-Edge.git
cd HomeAssistant-Edge
```

### 2️⃣ 安装依赖（Python 3.9+）
```bash
pip install -r requirements.txt
```

### 3️⃣ 创建 `.env` 文件
```ini
# Home Assistant
HA_BASE_URL=http://192.168.1.100:8123
HA_TOKEN=your_long_lived_access_token

# 本地 ASR API
ASR_API_URL=http://192.168.1.101:8001/recognize

# 本地 LLM API
LLM_BASE_URL=http://192.168.1.101:8000/v1
LLM_API_KEY=sk-xxxx
LLM_MODEL=qwen2.5-1.5B-p1024-ha-ax650
```

📌 注意事项：
- `HA_TOKEN` 在 Home Assistant **用户设置 → 安全** 中生成。
- **ASR**、**LLM** 和 **Home Assistant** 服务需在同一局域网内可访问。
- **ASR 与 LLM 必须运行在 AX650 芯片设备上**。

---

### 4️⃣ 配置设备 (`devices.yaml`)

`devices.yaml` 决定了可被控制的设备与对应服务。

示例：
```yaml
services:
  - name: light.turn_on
    params: ["rgb_color", "brightness"]
  - name: light.turn_off
  - name: cover.open
  - name: cover.close

devices:
  - id: light.livingroom
    name: "Livingroom Light"
    state: "on"
    brightness: 80
  - id: light.kitchen
    name: "Kitchen Light"
    state: "off"
```

💡 提示：  
- `id` 为 Home Assistant 的实体 ID  
- `name` 为该设备的语音控制名称（口语化）  
例如：“打开客厅和厨房的灯” 可被同时识别执行。

---

## 🛠 添加自定义设备

通过编辑 `devices.yaml` 可拓展更多设备，如空调、风扇等。

1. 打开 Home Assistant → 开发者工具 → 状态，获取设备实体 ID。  
2. 打开开发者工具 → 服务，查看支持的操作和参数。  
3. 将信息添加至 `devices.yaml` 并重启项目。

---

## ▶️ 运行
```bash
python main.py
```
命令行提示：
```
Home Assistant Controller - Press SPACE to start/stop recording
```
- **空格键** 开始/结束录音  
- 系统依次执行：ASR → 文本 → LLM → 控制命令生成 → Home Assistant 调用  
- **ESC** 退出程序

---

## 💡 示例
**语音指令：**
```
Turn on the living room and kitchen lights
```

**执行结果：**
```
Assistant: Sure, turning on the living room and kitchen lights.
Executing: [
  {"service": "light.turn_on", "target_device": "light.livingroom"},
  {"service": "light.turn_on", "target_device": "light.kitchen"}
]
```

> 当前支持中英文同时识别（英文效果最佳）。

---

## 📁 项目结构
```
HomeAssistant-Edge/
├── main.py              # 程序入口：录音、ASR 调用、LLM 调用
├── ha_control.py        # Home Assistant API 控制封装
├── chat.py              # LLM 调用与指令生成逻辑
├── config.py            # 环境与设备配置
├── devices.yaml         # 用户定义的设备与服务映射
├── requirements.txt     # Python 依赖
└── README.md
```

---

## ⚠️ 注意事项
- 当前中英文命令均可使用，英文识别与生成效果更佳  
- 尚未支持“所有设备”类指令（如“打开所有的灯”）  
- 已验证的设备类型列表见上文  
- 确保 Home Assistant API 已开启  
- 录音功能依赖 `pyaudio`，请确保麦克风可用  

---

## 📜 License
MIT License - 详见 [LICENSE](LICENSE)

---

## 🤝 贡献
欢迎通过 **Issue** 或 **Pull Request** 参与改进！

---

## 👤 作者
- [yuyun2000](https://github.com/yuyun2000)  
- [🌐 项目主页](https://github.com/yuyun2000/HomeAssistant-Edge)