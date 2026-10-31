import logging
import os
import re
from netmiko import ConnectHandler
from ntc_templates.parse import parse_output

logger = logging.getLogger(__name__)

def _connect(router):
    return ConnectHandler(
        device_type="cisco_ios",
        host=router,
        username=os.getenv("ROUTER_USER", ""),
        password=os.getenv("ROUTER_PASS", ""),
        conn_timeout=15,
        auth_timeout=15,
        banner_timeout=15,
    )

def _handle_error(e):
    name = type(e).__name__
    if isinstance(e, PermissionError) or "Authentication" in name:
        return {"status": "error", "result": "authentication_failed"}
    if isinstance(e, ConnectionError) or "Timeout" in name or "SSH" in name or "EOF" in name:
        return {"status": "error", "result": "connection_failed"}
    return {"status": "error", "result": "backend_failed"}

def _records(command, output):
    """TextFSM parser; returns [] when IOS reports '%' (e.g. interface is absent)."""
    if not output or "%" in output:
        return []
    try:
        res = parse_output(platform="cisco_ios", command=command, data=output)
        return res if isinstance(res, list) else []
    except Exception:
        return []

def _split_name(name):
    match = re.match(r"([A-Za-z-]+)\s*(.*)", str(name).strip())
    return (match.group(1).lower(), match.group(2)) if match else ("", str(name))

def _same_name(a, b):
    """Returns True for Loopback123 vs Lo123 (Cisco abbreviations)."""
    (pa, ra), (pb, rb) = _split_name(a), _split_name(b)
    return ra == rb and (pa.startswith(pb) or pb.startswith(pa))

def _collect(conn, interface_name):
    ip_cmd = f"show ip interface {interface_name}"
    desc_cmd = "show interfaces description"
    out_ip = conn.send_command(ip_cmd)
    out_desc = conn.send_command(desc_cmd)
    return _records(ip_cmd, out_ip), _records(desc_cmd, out_desc)

def _normalize(interface_name, ip_info, descriptions):
    ip_entry = next((r for r in (ip_info or []) if _same_name(r.get("interface", ""), interface_name)), None)
    desc_entry = next((r for r in (descriptions or []) if _same_name(r.get("port", ""), interface_name)), None)

    if ip_entry is None and desc_entry is None:
        return None

    ipv4 = None
    if ip_entry:
        ip_val = ip_entry.get("ip_address")
        prefix_val = ip_entry.get("prefix_length")
        
        if isinstance(ip_val, list) and ip_val:
            ip_val = ip_val[0]
        if isinstance(prefix_val, list) and prefix_val:
            prefix_val = prefix_val[0]
            
        if ip_val and prefix_val:
            ipv4 = f"{ip_val}/{prefix_val}"

    admin_down = False
    if ip_entry:
        status_str = str(ip_entry.get("link_status", "")).lower()
        admin_down = "administratively down" in status_str or "admin down" in status_str
    elif desc_entry:
        status_str = str(desc_entry.get("status", "")).lower()
        admin_down = "admin" in status_str and "down" in status_str

    description = None
    if desc_entry:
        desc_val = desc_entry.get("description")
        if desc_val:
            description = desc_val.strip()

    return {
        "name": interface_name,
        "ipv4": ipv4,
        "description": description or None,
        "admin_state": "down" if admin_down else "up",
    }

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
            with _connect(router) as conn:
                ip_info, descriptions = _collect(conn, interface_name)

        interface = _normalize(interface_name, ip_info, descriptions)
        if interface is None:
            return {"status": "ok", "result": "not_found", "interface": None}

        return {
            "status": "ok",
            "result": "found",
            "interface": interface,
        }
    except Exception as e:
        logger.exception("Error in get_interface_state: %s", e)
        return _handle_error(e)

def _real_delete(router, interface_name):
    with _connect(router) as conn:
        # 1. ตรวจสอบก่อนว่ามี interface นี้อยู่จริงไหมก่อนลบ
        ip_info, descriptions = _collect(conn, interface_name)
        if _normalize(interface_name, ip_info, descriptions) is None:
            return "not_found"

        # 2. ส่งคำสั่งลบ interface
        conn.send_config_set([f"no interface {interface_name}"])

        # 3. ลบสำเร็จเรียบร้อย
        return "deleted"

def delete_interface(
    router,
    interface_name,
    netmiko_delete=None,
):
    """Delete an interface using Netmiko."""
    try:
        if netmiko_delete is not None:
            res = netmiko_delete(router, interface_name)
        else:
            res = _real_delete(router, interface_name)

        if res == "deleted":
            return {"status": "ok", "result": "deleted"}
        elif res == "not_found":
            return {"status": "ok", "result": "not_found", "interface": None}
        else:
            return {"status": "error", "result": "backend_failed"}
    except Exception as e:
        logger.exception("Error in delete_interface: %s", e)
        return _handle_error(e)
