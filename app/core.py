import yaml

ALLOWED_ROUTERS = {
    "10.0.29.101",
    "10.0.29.102",
    "10.0.29.103",
    "10.0.29.104",
    "10.0.29.105",
}

METHODS = {
    "restconf": {"status", "plan", "apply"},
    "netconf": {"status", "plan", "apply"},
    "ansible": {"apply"},
    "netmiko-textfsm": {"status", "delete"},
}

def _blank(value):
    return value is None or (isinstance(value, str) and not value.strip())

def validate_request(data):
    """
    Validate one IPA2026 desired-state request.

    Return a response dictionary according to
    specs/response-spec-v1.md.
    """
    if not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}

    version = data.get("version")
    if type(version) is not int or version != 1:
        return {"status": "error", "result": "invalid_version"}

    if _blank(data.get("router")):
        return {"status": "error", "result": "missing_router"}
    if not isinstance(data["router"], str) or data["router"] not in ALLOWED_ROUTERS:
        return {"status": "error", "result": "invalid_router"}

    if _blank(data.get("method")):
        return {"status": "error", "result": "missing_method"}
    method = data["method"]
    if not isinstance(method, str) or method not in METHODS:
        return {"status": "error", "result": "invalid_method"}

    if _blank(data.get("action")):
        return {"status": "error", "result": "missing_action"}
    action = data["action"]
    if not isinstance(action, str) or action not in METHODS[method]:
        return {"status": "error", "result": "invalid_action"}

    desired = data.get("desired")
    if not isinstance(desired, dict):
        return {"status": "error", "result": "missing_desired"}

    interface = desired.get("interface")
    if not isinstance(interface, dict):
        return {"status": "error", "result": "missing_interface"}

    name = interface.get("name")
    if not isinstance(name, str) or not name.strip():
        return {"status": "error", "result": "missing_interface_name"}

    if action in {"plan", "apply"}:
        for field in ("ipv4", "description", "admin_state"):
            if _blank(interface.get(field)):
                return {"status": "error", "result": f"missing_{field}"}
        if interface["admin_state"] not in {"up", "down"}:
            return {"status": "error", "result": "invalid_admin_state"}

    return {"status": "ok", "result": "accepted"}

def process_request_file(path):
    """
    Read a YAML request file, validate it,
    and return a response dictionary.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {"status": "error", "result": "invalid_yaml"}
    if not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}
    return validate_request(data)
