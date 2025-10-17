import requests
import ast
from config import HA_BASE_URL, HA_TOKEN

def call_service(domain, service, data):
    """
    控制 Home Assistant 实体的泛用函数。
    :param domain: 服务域，比如 'light'
    :param service: 服务名，比如 'turn_on', 'turn_off'
    :param data: 需要提交的数据（dict）
    :return: 返回 JSON 数据（dict），如出错返回 None
    """
    url = f"{HA_BASE_URL.rstrip('/')}/api/services/{domain}/{service}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"请求出错: {e}")
        return None

def get_state(entity_id):
    """
    查询实体状态。
    :param entity_id: 实体ID
    :return: 状态字典，出错返回None
    """
    url = f"{HA_BASE_URL.rstrip('/')}/api/states/{entity_id}"
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"查询状态出错: {e}")
        return None

# ------------------------ Light ------------------------
def control_light(entity_id, action, **kwargs):
    if action == "on":
        data = {"entity_id": entity_id}
        if "brightness" in kwargs and  not isinstance(kwargs["brightness"], dict):
            data["brightness"] = int(kwargs["brightness"]*255) if kwargs["brightness"]<=1 else kwargs["brightness"]
        return call_service("light", "turn_on", data)
    elif action == "off":
        data = {"entity_id": entity_id}
        return call_service("light", "turn_off", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到灯的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        onoff = "打开" if state.get("state") == "on" else "关闭"
        brightness = attr.get("brightness")
        color_mode = attr.get("color_mode")
        available = "是" if attr.get("available", True) else "否"
        msg = f'灯“{name}”当前状态为：{onoff}。'
        if brightness is not None:
            msg += f"\n- 亮度：{brightness}（范围0-255）"
        if color_mode:
            msg += f"\n- 颜色模式：{color_mode}"
        msg += f"\n- 设备可用：{available}"
        return msg
    elif action == "color":
        data = {"entity_id": entity_id}
        if "color_name" in kwargs:
            data["color_name"] = kwargs["color_name"]
        elif "rgb_color" in kwargs:
            rgb_color = ast.literal_eval(kwargs["rgb_color"]) if isinstance(kwargs["rgb_color"], str) else kwargs["rgb_color"]
            data["rgb_color"] = rgb_color
        else:
            print("请提供color_name或rgb_color参数")
            return None
        return call_service("light", "turn_on", data)
    else:
        print("不支持的操作类型。action应为'on', 'off', 'state', 'color'")
        return None

# ------------------------ Cover ------------------------
def control_curtain(entity_id, action, position=None):
    if action == "open":
        data = {"entity_id": entity_id}
        return call_service("cover", "open_cover", data)
    elif action == "close":
        data = {"entity_id": entity_id}
        return call_service("cover", "close_cover", data)
    elif action == "position":
        if position is None or not (0 <= position <= 100):
            print("请提供0-100之间的position参数")
            return None
        data = {"entity_id": entity_id, "position": position}
        return call_service("cover", "set_cover_position", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到窗帘的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        onoff = "打开" if state.get("state") == "open" else "关闭"
        pos = attr.get("current_position")
        available = "是" if attr.get("available", True) else "否"
        msg = f'窗帘“{name}”当前状态为：{onoff}'
        if pos is not None:
            msg += f"，位置为{pos}%"
        msg += f"。\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'open', 'close', 'position', 'state'")
        return None

# ------------------------ Fan ------------------------
def control_fan(entity_id, action):
    if action == "on":
        data = {"entity_id": entity_id}
        return call_service("fan", "turn_on", data)
    elif action == "off":
        data = {"entity_id": entity_id}
        return call_service("fan", "turn_off", data)
    elif action == "increase_speed":
        data = {"entity_id": entity_id}
        return call_service("fan", "increase_speed", data)
    elif action == "decrease_speed":
        data = {"entity_id": entity_id}
        return call_service("fan", "decrease_speed", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到风扇的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        onoff = "开启" if state.get("state") == "on" else "关闭"
        percentage = attr.get("percentage")
        preset_mode = attr.get("preset_mode")
        available = "是" if attr.get("available", True) else "否"
        msg = f'风扇“{name}”当前状态为：{onoff}。'
        if percentage is not None:
            msg += f"\n- 百分比速度：{percentage}%"
        if preset_mode:
            msg += f"\n- 预设模式：{preset_mode}"
        msg += f"\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'on', 'off', 'increase_speed','decrease_speed', 'state'")
        return None

# ------------------------ Climate ------------------------
def control_climate(entity_id, action, **kwargs):
    if action == "set_temperature":
        if "temperature" not in kwargs:
            print("缺少temperature参数")
            return None
        data = {"entity_id": entity_id, "temperature": kwargs["temperature"]}
        return call_service("climate", "set_temperature", data)
    elif action == "set_fan_mode":
        if "fan_mode" not in kwargs:
            print("缺少fan_mode参数")
            return None
        data = {"entity_id": entity_id, "fan_mode": kwargs["fan_mode"]}
        return call_service("climate", "set_fan_mode", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到空调的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        hvac_action = attr.get("hvac_action", "unknown")
        temperature = attr.get("temperature")
        current_temp = attr.get("current_temperature")
        fan_mode = attr.get("fan_mode")
        available = "是" if attr.get("available", True) else "否"
        msg = f'空调“{name}”当前状态为：{hvac_action}。'
        if temperature is not None:
            msg += f"\n- 设置温度：{temperature}℃"
        if current_temp is not None:
            msg += f"\n- 当前室温：{current_temp}℃"
        if fan_mode:
            msg += f"\n- 风扇模式：{fan_mode}"
        msg += f"\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'set_temperature', 'set_fan_mode', 'state'")
        return None

# ------------------------ Lock ------------------------
def control_lock(entity_id, action):
    if action == "lock":
        data = {"entity_id": entity_id}
        return call_service("lock", "lock", data)
    elif action == "unlock":
        data = {"entity_id": entity_id}
        return call_service("lock", "unlock", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到门锁的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        locked = "锁定" if state.get("state") == "locked" else "未锁定"
        available = "是" if attr.get("available", True) else "否"
        msg = f'门锁“{name}”当前状态为：{locked}。'
        msg += f"\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'lock', 'unlock', 'state'")
        return None

# ------------------------ Media Player ------------------------
def control_media_player(entity_id, action):
    if action == "play":
        data = {"entity_id": entity_id}
        return call_service("media_player", "media_play", data)
    elif action == "pause":
        data = {"entity_id": entity_id}
        return call_service("media_player", "media_pause", data)
    elif action == "stop":
        data = {"entity_id": entity_id}
        return call_service("media_player", "media_stop", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到媒体播放器的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        media_title = attr.get("media_title")
        volume_level = attr.get("volume_level")
        is_playing = state.get("state") == "playing"
        available = "是" if attr.get("available", True) else "否"
        msg = f'媒体播放器“{name}”当前状态为：{"播放中" if is_playing else "暂停"}。'
        if media_title:
            msg += f"\n- 正在播放：{media_title}"
        if volume_level is not None:
            msg += f"\n- 音量：{int(volume_level * 100)}%"
        msg += f"\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'play', 'pause', 'stop', 'state'")
        return None

# ------------------------ Switch ------------------------
def control_switch(entity_id, action):
    if action == "on":
        data = {"entity_id": entity_id}
        return call_service("switch", "turn_on", data)
    elif action == "off":
        data = {"entity_id": entity_id}
        return call_service("switch", "turn_off", data)
    elif action == "state":
        state = get_state(entity_id)
        if not state or "attributes" not in state:
            return "未能获取到开关的状态信息。"
        attr = state["attributes"]
        name = attr.get("friendly_name", entity_id)
        onoff = "开启" if state.get("state") == "on" else "关闭"
        available = "是" if attr.get("available", True) else "否"
        msg = f'开关“{name}”当前状态为：{onoff}。'
        msg += f"\n- 设备可用：{available}"
        return msg
    else:
        print("不支持的操作类型。action应为'on', 'off', 'state'")
        return None
    

import time
# 示例测试
if __name__ == "__main__":
    # Light
    # print(control_light("light.livingroom", "on"))
    # time.sleep(1)
    # print(control_light("light.livingroom", "off"))
    print(control_light("light.livingroom", "on",brightness=0.0))
    # print(control_light("light.livingroom", "color",rgb_color='(255,0,0)'))

    # # Curtain
    # print(control_curtain("cover.test_cover_cover", "open"))
    # print(control_curtain("cover.livingroom_curtain", "close"))
    # print(control_curtain("cover.livingroom_curtain", "state"))

    # # Fan
    # print(control_fan("fan.bedroom_fan", "on"))
    # print(control_fan("fan.test_fan", "decrease_speed"))
    # print(control_fan("fan.test_fan", "state"))

    # # Climate
    # print(control_climate("climate.livingroom_ac", "set_temperature", temperature=22))
    # print(control_climate("climate.livingroom_ac", "set_fan_mode", fan_mode="high"))
    # print(control_climate("climate.livingroom_ac", "state"))

    # # Lock
    # print(control_lock("lock.test_front_door_lock", "lock"))
    # time.sleep(1)
    # print(control_lock("lock.test_front_door_lock", "unlock"))
    # print(control_lock("lock.test_front_door_lock", "state"))

    # # Media Player
    # print(control_media_player("media_player.livingroom_speaker", "play"))
    # print(control_media_player("media_player.livingroom_speaker", "pause"))
    # print(control_media_player("media_player.livingroom_speaker", "state"))

    # # Switch
    # print(control_switch("switch.coffee_machine", "on"))
    # time.sleep(1)
    # print(control_switch("switch.coffee_machine", "off"))
    # print(control_switch("switch.coffee_machine", "state"))