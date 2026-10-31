import os
from ipaddress import IPv4Interface
import requests
import urllib3

from app.backends.planning import plan_interface as generic_plan_interface

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "Accept": "application/yang-data+json",
    "Content-Type": "application/yang-data+json",
}
def _get_auth():
    return (os.getenv("ROUTER_USER", ""), os.getenv("ROUTER_PASS", ""))

# ดึงสถานะ interface ผ่าน RESTCONF
def get_interface_state(
    router,
    interface_name,
    http_get=None,
):
    """Return normalized interface status using RESTCONF."""
    url = f"https://{router}/restconf/data/ietf-interfaces:interfaces/interface={interface_name}"

    try:
        if http_get is not None:
            response = http_get(url)
        else:
            response = requests.get(
                url,
                auth=_get_auth(),
                headers=HEADERS,
                verify=False,
                timeout=10,
            )
        if response.status_code == 200:
            data = response.json()
            iface = data.get("ietf-interfaces:interface", {})
            name = iface.get("name", interface_name)
            description = iface.get("description")
            enabled = iface.get("enabled", True)
            admin_state = "up" if enabled else "down"
            ipv4 = None
            addresses = iface.get("ietf-ip:ipv4", {}).get("address", [])
            if addresses:
                ip = addresses[0].get("ip")
                netmask = addresses[0].get("netmask")
                if ip and netmask:
                    ipv4 = f"{ip}/{IPv4Interface(f'{ip}/{netmask}').network.prefixlen}"
            return {
                "status": "ok",
                "result": "found",
                "interface": {
                    "name": name,
                    "ipv4": ipv4,
                    "description": description,
                    "admin_state": admin_state,
                },
            }
        elif response.status_code == 404:
            return {
                "status": "ok",
                "result": "not_found",
                "interface": None,
            }
        elif response.status_code in (401, 403):
            return {"status": "error", "result": "authentication_failed"}
        else:
            return {"status": "error", "result": "backend_failed"}
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    except (ConnectionError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return {"status": "error", "result": "connection_failed"}
    except Exception:
        return {"status": "error", "result": "backend_failed"}

def plan_interface(
    router,
    desired_interface,
    http_get=None,
):
    """Return create/update/no_change plan using RESTCONF status."""
    return generic_plan_interface(
        router,
        desired_interface,
        lambda r, name: get_interface_state(r, name, http_get=http_get),
    )

def apply_interface(
    router,
    desired_interface,
    http_put=None,
):
    """Apply complete desired interface state using RESTCONF."""
    name = desired_interface["name"]
    number = int(name[len("Loopback"):])
    url = f"https://{router}/restconf/data/Cisco-IOS-XE-native:native/interface/Loopback={number}"
    ipv4_obj = IPv4Interface(desired_interface["ipv4"])
    payload_loopback = {
        "name": number,
        "description": desired_interface["description"],
        "ip": {
            "address": {
                "primary": {
                    "address": str(ipv4_obj.ip),
                    "mask": str(ipv4_obj.network.netmask),
                }
            }
        },
    }
    if desired_interface.get("admin_state") == "down":
        payload_loopback["shutdown"] = [None]
    payload = {"Cisco-IOS-XE-native:Loopback": payload_loopback}
    try:
        if http_put is not None:
            response = http_put(url, json=payload)
        else:
            response = requests.put(
                url,
                auth=_get_auth(),
                headers=HEADERS,
                json=payload,
                verify=False,
                timeout=10,
            )

        if response.status_code in (200, 201, 204):
            return {"status": "ok", "result": "applied"}
        
        elif response.status_code in (401, 403):
            return {"status": "error", "result": "authentication_failed"}
        
        else:
            return {"status": "error", "result": "backend_failed"}
        
    except PermissionError:
        return {"status": "error", "result": "authentication_failed"}
    
    except (ConnectionError, requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return {"status": "error", "result": "connection_failed"}

    except Exception:
        return {"status": "error", "result": "backend_failed"}
