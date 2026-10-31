import os
from netmiko import ConnectHandler

def _get_device(router):
    return {
        "device_type": "cisco_ios",
        "host": router,
        "username": os.getenv("ROUTER_USER", ""),
        "password": os.getenv("ROUTER_PASS", ""),
        "timeout": 10,
    }

def _handle_error(e):
    name = type(e).__name__
    if isinstance(e, PermissionError) or "Authentication" in name:
        return {"status": "error", "result": "authentication_failed"}

    if isinstance(e, ConnectionError) or "Timeout" in name or "SSH" in name:
        return {"status": "error", "result": "connection_failed"}

    return {"status": "error", "result": "backend_failed"}

def get_interface_state(
    router,
    interface_name,
    netmiko_get=None,
):
    """Return normalized interface status using Netmiko + TextFSM."""
    try:
        if netmiko_get is not None:
            ip_info, descriptions = netmiko_get(router, interface_name)
        else:
            with ConnectHandler(**_get_device(router)) as conn:
                ip_info = conn.send_command(f"show ip interface {interface_name}", use_textfsm=True)
                descriptions = conn.send_command("show interfaces description", use_textfsm=True)
        # ถ้าไม่พบข้อมูล หรือ list ว่าง แปลว่าไม่มี interface นี้
        if not ip_info or not isinstance(ip_info, list):
            return {"status": "ok", "result": "not_found", "interface": None}
        entry = ip_info[0]
        # ตรวจสอบ admin_state: ถ้ามีคำว่า administratively down แปลว่า down นอกนั้น up
        link_status = str(entry.get("link_status", "")).lower()
        admin_state = "down" if "administratively down" in link_status or "admin down" in link_status else "up"
        # ดึง IPv4 / Prefix
        ipv4 = None
        ip_list = entry.get("ip_address") or []
        prefix_list = entry.get("prefix_length") or []
        if ip_list and prefix_list:
            ipv4 = f"{ip_list[0]}/{prefix_list[0]}"
        # ดึง Description โดยจับคู่ชื่อเต็ม หรือชื่อย่อ เช่น Lo123
        number = interface_name[len("Loopback"):] if interface_name.lower().startswith("loopback") else ""
        short_name = f"lo{number}".lower()
        full_name = interface_name.lower()
        description = None
        for desc_entry in (descriptions or []):
            port = str(desc_entry.get("port", "")).lower()
            if port in (full_name, short_name):
                description = desc_entry.get("description")
                break
        return {
            "status": "ok",
            "result": "found",
            "interface": {
                "name": interface_name,
                "ipv4": ipv4,
                "description": description,
                "admin_state": admin_state,
            },
        }
    except Exception as e:
        return _handle_error(e)

def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""
    try:
        if netmiko_delete is not None:
            res = netmiko_delete(router, interface_name)
            if res == "deleted":
                return {"status": "ok", "result": "deleted"}

            elif res == "not_found":
                return {"status": "ok", "result": "not_found", "interface": None}

            else:
                return {"status": "error", "result": "backend_failed"}

        st = get_interface_state(router, interface_name)
        if st.get("status") == "error":
            return st

        if st.get("result") == "not_found":
            return {"status": "ok", "result": "not_found", "interface": None}

        with ConnectHandler(**_get_device(router)) as conn:
            conn.send_config_set([f"no interface {interface_name}"])

        verify_st = get_interface_state(router, interface_name)
        if verify_st.get("result") == "not_found":
            return {"status": "ok", "result": "deleted"}
        return {"status": "error", "result": "backend_failed"}
    except Exception as e:
        return _handle_error(e)
