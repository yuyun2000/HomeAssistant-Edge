import csv
import yaml

# 测试用例定义（这里是覆盖性测试）
test_cases = [
    # 灯 light
    {
        "id": "L-01",
        "category": "light",
        "voice_command": "Turn on the living room light",
        "expected_service": "light.turn_on",
        "target_device": "light.livingroom",
        "expected_params": "",
        "llm_expected_reply": "Sure, turning on the Livingroom Light."
    },
    {
        "id": "L-02",
        "category": "light",
        "voice_command": "Turn off the bedroom light",
        "expected_service": "light.turn_off",
        "target_device": "light.bedroom",
        "expected_params": "",
        "llm_expected_reply": "Okay, turning off the Bedroom Light."
    },
    {
        "id": "L-03",
        "category": "light",
        "voice_command": "Set the living room light to 50 percent brightness",
        "expected_service": "light.turn_on",
        "target_device": "light.livingroom",
        "expected_params": "brightness=50",
        "llm_expected_reply": "Dimming the Livingroom Light to 50% brightness."
    },
    {
        "id": "L-04",
        "category": "light",
        "voice_command": "Change the living room light to blue",
        "expected_service": "light.turn_on",
        "target_device": "light.livingroom",
        "expected_params": "rgb_color=[0,0,255]",
        "llm_expected_reply": "Changing the Livingroom Light to blue."
    },
    # 窗帘 cover
    {
        "id": "B-01",
        "category": "cover",
        "voice_command": "Open the living room curtain",
        "expected_service": "cover.open_cover",
        "target_device": "cover.livingroom_curtain",
        "expected_params": "",
        "llm_expected_reply": "Opening the Living Room Curtain."
    },
    {
        "id": "B-02",
        "category": "cover",
        "voice_command": "Close the living room curtain",
        "expected_service": "cover.close_cover",
        "target_device": "cover.livingroom_curtain",
        "expected_params": "",
        "llm_expected_reply": "Closing the Living Room Curtain."
    },
    # 风扇 fan
    {
        "id": "F-01",
        "category": "fan",
        "voice_command": "Turn on the bedroom fan",
        "expected_service": "fan.turn_on",
        "target_device": "fan.bedroom_fan",
        "expected_params": "",
        "llm_expected_reply": "Turning on the Bedroom Fan."
    },
    {
        "id": "F-02",
        "category": "fan",
        "voice_command": "Increase the bedroom fan speed",
        "expected_service": "fan.increase_speed",
        "target_device": "fan.bedroom_fan",
        "expected_params": "",
        "llm_expected_reply": "Increasing the speed of the Bedroom Fan."
    },
    # 空调 climate
    {
        "id": "C-01",
        "category": "climate",
        "voice_command": "Set the AC to 22 degrees Celsius",
        "expected_service": "climate.set_temperature",
        "target_device": "climate.livingroom_ac",
        "expected_params": "temperature=22",
        "llm_expected_reply": "Setting the Living Room AC to 22 degrees Celsius."
    },
    {
        "id": "C-02",
        "category": "climate",
        "voice_command": "Set AC fan to high",
        "expected_service": "climate.set_fan_mode",
        "target_device": "climate.livingroom_ac",
        "expected_params": "fan_mode=high",
        "llm_expected_reply": "Setting the fan of Living Room AC to high."
    },
    # 门锁 lock
    {
        "id": "LK-01",
        "category": "lock",
        "voice_command": "Lock the front door",
        "expected_service": "lock.lock",
        "target_device": "lock.front_door",
        "expected_params": "",
        "llm_expected_reply": "Locking the Front Door."
    },
    {
        "id": "LK-02",
        "category": "lock",
        "voice_command": "Unlock the front door",
        "expected_service": "lock.unlock",
        "target_device": "lock.front_door",
        "expected_params": "",
        "llm_expected_reply": "Unlocking the Front Door."
    },
    # 媒体播放器 media_player
    {
        "id": "M-01",
        "category": "media_player",
        "voice_command": "Play music on the living room speaker",
        "expected_service": "media_player.media_play",
        "target_device": "media_player.livingroom_speaker",
        "expected_params": "",
        "llm_expected_reply": "Starting playback on Living Room Speaker."
    },
    {
        "id": "M-02",
        "category": "media_player",
        "voice_command": "Pause the music on the living room speaker",
        "expected_service": "media_player.media_pause",
        "target_device": "media_player.livingroom_speaker",
        "expected_params": "",
        "llm_expected_reply": "Pausing the Living Room Speaker."
    },
    # 开关 switch
    {
        "id": "S-01",
        "category": "switch",
        "voice_command": "Turn on the coffee machine",
        "expected_service": "switch.turn_on",
        "target_device": "switch.coffee_machine",
        "expected_params": "",
        "llm_expected_reply": "Turning on the Coffee Machine."
    },
    {
        "id": "S-02",
        "category": "switch",
        "voice_command": "Turn off the coffee machine",
        "expected_service": "switch.turn_off",
        "target_device": "switch.coffee_machine",
        "expected_params": "",
        "llm_expected_reply": "Turning off the Coffee Machine."
    },
]

# 导出 CSV
with open("test_cases.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "id", "category", "voice_command", "expected_service", "target_device", "expected_params", "llm_expected_reply"
    ])
    writer.writeheader()
    writer.writerows(test_cases)

# 生成 devices.yaml
devices_dict = {"services": [], "devices": []}
services_set = set()
devices_set = set()

for case in test_cases:
    # 添加服务
    if case["expected_params"]:
        # 提取参数名
        param_names = [p.split("=")[0] for p in case["expected_params"].split(",")]
    else:
        param_names = []
    if case["expected_service"] not in services_set:
        devices_dict["services"].append({"name": case["expected_service"], "params": param_names} if param_names else {"name": case["expected_service"]})
        services_set.add(case["expected_service"])
    # 添加设备
    if case["target_device"] not in devices_set:
        devices_dict["devices"].append({
            "id": case["target_device"],
            "name": case["target_device"].split(".")[1].replace("_", " ").title(),
            "state": "off"  # 默认状态
        })
        devices_set.add(case["target_device"])

with open("devices.yaml", "w", encoding="utf-8") as f:
    yaml.dump(devices_dict, f, allow_unicode=True)

print("✅ 已生成 test_cases.csv 和 devices.yaml")