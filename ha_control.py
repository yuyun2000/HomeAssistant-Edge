import requests
from config import HA_BASE_URL, HA_TOKEN
# 本地配置：请根据实际情况修改

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

def control_light(entity_id, action, **kwargs):
    """
    统一灯光控制接口，外部只需调用此函数。
    :param entity_id: 灯光实体ID，如 'light.test_light'
    :param action: 操作类型，'on'开灯，'off'关灯，'state'查状态，'color'设颜色
    :param kwargs: 额外参数，如 color_name, rgb_color, brightness
    :return: 操作结果或状态
    """
    if action == "on":
        data = {"entity_id": entity_id}
        if "brightness" in kwargs:
            data["brightness"] = kwargs["brightness"]
        if "color_name" in kwargs:
            data["color_name"] = kwargs["color_name"]
        if "rgb_color" in kwargs:
            data["rgb_color"] = kwargs["rgb_color"]
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
            data["rgb_color"] = kwargs["rgb_color"]
        else:
            print("请提供color_name或rgb_color参数")
            return None
        return call_service("light", "turn_on", data)
    else:
        print("不支持的操作类型。action应为'on', 'off', 'state', 'color'")
        return None

def control_curtain(entity_id, action, position=None):
    """
    统一窗帘控制接口，外部只需调用此函数。
    :param entity_id: 窗帘实体ID，如 'cover.test_curtain'
    :param action: 操作类型，'open'全开，'close'全关，'position'指定角度（0-100）
    :param position: 角度百分比（0-100），仅在action='position'时生效
    :return: 操作结果或状态
    """
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

# 用法示例（外部import后只需调用control_light/control_curtain）：
# from light_api import control_light, control_curtain
# control_light("light.test_light", "on")
# control_light("light.test_light", "off")
# state = control_light("light.test_light", "state")
# control_light("light.test_light", "color", color_name="blue")
# control_curtain("cover.test_curtain", "open")
# control_curtain("cover.test_curtain", "close")
# control_curtain("cover.test_curtain", "position", position=50)
# state = control_curtain("cover.test_curtain", "state")
