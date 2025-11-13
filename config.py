# config.py
import os
import yaml
from dotenv import load_dotenv

# 加载.env环境变量
load_dotenv()

# API配置
HA_BASE_URL = os.getenv("HA_BASE_URL", "http://localhost:8123")
HA_TOKEN = os.getenv("HA_TOKEN", "")
ASR_API_URL = os.getenv("ASR_API_URL", "http://localhost:8001/recognize")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8000/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

# 读取设备配置
def load_device_config(path="devices.yaml"):
    if not os.path.exists(path):
        raise FileNotFoundError(f"设备配置文件 {path} 未找到")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

DEVICE_CONFIG = load_device_config()

# 根据配置生成 system_prompt
def generate_system_prompt():
    services_str = "\n".join(
        f"{svc['name']}({','.join(svc.get('params', []))})" if svc.get('params') else svc['name']
        for svc in DEVICE_CONFIG['services']
    )

    devices_str = "\n".join(
        f"{dev['id']} '{dev['name']}'"
        + (f";{dev['brightness']}%" if 'brightness' in dev else "")
        for dev in DEVICE_CONFIG['devices']
    )

    return f"""
You are 'm5', a helpful AI Assistant that controls the devices in a house.
Complete the task as instructed or answer the question with the provided information only.

Services:
{services_str}

Devices:
{devices_str}
""".strip()

SYSTEM_PROMPT = generate_system_prompt()