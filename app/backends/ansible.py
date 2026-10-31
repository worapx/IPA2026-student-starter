import json
import os
import subprocess
from ipaddress import IPv4Interface
from pathlib import Path

def _handle_error(e):
    name = type(e).__name__
    if isinstance(e, PermissionError) or "Authentication" in name:
        return {"status": "error", "result": "authentication_failed"}
    
    if isinstance(e, ConnectionError) or "Unreachable" in name or "Timeout" in name:
        return {"status": "error", "result": "connection_failed"}
    
    return {"status": "error", "result": "backend_failed"}

def apply_interface(
    router,
    desired_interface,
    run_playbook=None,
):
    """Apply complete desired interface state using Ansible."""
    ip_obj = IPv4Interface(desired_interface["ipv4"])
    variables = {
        "router": router,
        "interface_name": desired_interface["name"],
        "description": desired_interface["description"],
        "ipv4_address": str(ip_obj.ip),
        "netmask": str(ip_obj.network.netmask),
        "shutdown": (desired_interface.get("admin_state") == "down"),
    }

    try:
        if run_playbook is not None:
            run_playbook(variables)
        else:
            repo_root = Path(__file__).resolve().parents[2]
            playbook_path = repo_root / "ansible" / "apply_interface.yml"
            inventory_path = repo_root / "ansible" / "inventory.ini"
            env = os.environ.copy()
            env["ANSIBLE_HOST_KEY_CHECKING"] = "False"
            cmd = [
                "ansible-playbook",
                "-i", str(inventory_path),
                str(playbook_path),
                "-e", json.dumps(variables),
                "-e", f"ansible_host={router}",
                "-e", f"ansible_user={os.getenv('ROUTER_USER', '')}",
                "-e", f"ansible_password={os.getenv('ROUTER_PASS', '')}",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
    
            if res.returncode != 0:
                output = (res.stdout + res.stderr).lower()
                if "authentication failed" in output or "permission denied" in output:
                    return {"status": "error", "result": "authentication_failed"}
                
                if "timeout" in output:
                    return {"status": "error", "result": "connection_failed"}

                if "unreachable" in output:
                    return {"status": "error", "result": "connection_failed"}

                return {"status": "error", "result": "backend_failed"}
    
        return {"status": "ok", "result": "applied"}

    except Exception as e:
        return _handle_error(e)
