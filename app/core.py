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

def validate_request(data):
    """
    Validate one IPA2026 desired-state request.

    Return a response dictionary according to
    specs/response-spec-v1.md.
    """
    
    # ตรวจสอบว่า data เป็น dictionary หรือไม่
    if not isinstance(data, dict):
        return {"status": "error", "result": "invalid_yaml"}
    
    # ตรวจสอบว่า data มี version เป็น 1
    if "version" not in data or type(data["version"]) is not int or data["version"] != 1:
        return {"status": "error", "result": "invalid_version"}
    
    # ตรวจสอบว่า data มี router
    if "router" not in data or data["router"] is None:
        return {"status": "error", "result": "missing_router"}
    
    # ตรวจสอบว่า router อยู่ใน ALLOWED_ROUTERS
    if data["router"] not in ALLOWED_ROUTERS:
        return {"status": "error", "result": "invalid_router"}
    
    # ตรวจสอบว่า data มี method
    if "method" not in data or data["method"] is None:
        return {"status": "error", "result": "missing_method"}
    
    # ตรวจสอบว่า method อยู่ใน METHODS
    if data["method"] not in METHODS:
        return {"status": "error", "result": "invalid_method"}
    
    # ตรวจสอบว่า data มี action
    if "action" not in data or data["action"] is None:
        return {"status": "error", "result": "missing_action"}
    
    # ตรวจสอบว่า action อยู่ใน METHODS[method]
    if data["action"] not in METHODS[data["method"]]:
        return {"status": "error", "result": "invalid_action"}
    
    # ตรวจสอบว่า data มี desired
    if "desired" not in data or not isinstance(data["desired"], dict):
        return {"status": "error", "result": "missing_desired"}
    
    desired = data["desired"]
    if "interface" not in desired or not isinstance(desired["interface"], dict):
        return {"status": "error", "result": "missing_interface"}
    
    interface = desired["interface"]
    if "name" not in interface or not interface["name"]:
        return {"status": "error", "result": "missing_interface_name"}
    
    # ตรวจสอบว่า action เป็น plan หรือ apply และตรวจสอบค่าของ interface
    action = data["action"]
    if action in {"plan", "apply"}:
        if "ipv4" not in interface or interface["ipv4"] is None:
            return {"status": "error", "result": "missing_ipv4"}
        if "description" not in interface or interface["description"] is None:
            return {"status": "error", "result": "missing_description"}
        if "admin_state" not in interface or interface["admin_state"] is None:
            return {"status": "error", "result": "missing_admin_state"}
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
    return validate_request(data)
