import os
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from ipaddress import IPv4Interface
from ncclient import manager

from app.backends.planning import plan_interface as generic_plan_interface


NETCONF_NS = "urn:ietf:params:xml:ns:netconf:base:1.0"
IETF_IF_NS = "urn:ietf:params:xml:ns:yang:ietf-interfaces"
IETF_IP_NS = "urn:ietf:params:xml:ns:yang:ietf-ip"
NATIVE_NS = "http://cisco.com/ns/yang/Cisco-IOS-XE-native"

def _connect(router):
    return manager.connect(
        host=router,
        port=830,
        username=os.getenv("ROUTER_USER", ""),
        password=os.getenv("ROUTER_PASS", ""),
        hostkey_verify=False,
        timeout=10,
    )

def _handle_error(e):
    if isinstance(e, PermissionError) or "Authentication" in type(e).__name__:
        return {"status": "error", "result": "authentication_failed"}
    if isinstance(e, (ConnectionError, OSError)) or "SSH" in type(e).__name__ or "Timeout" in type(e).__name__:
        return {"status": "error", "result": "connection_failed"}
    return {"status": "error", "result": "backend_failed"}

def get_interface_state(
    router,
    interface_name,
    netconf_get_config=None,
):
    """Return normalized interface status using NETCONF."""
    filter_xml = f"""<interfaces xmlns="{IETF_IF_NS}">
  <interface>
    <name>{interface_name}</name>
  </interface>
</interfaces>"""
    
    try:
        if netconf_get_config is not None:
            xml_text = netconf_get_config(router, filter_xml)
        else:
            with _connect(router) as m:
                xml_text = m.get_config(source="running", filter=("subtree", filter_xml)).xml
 
        root = ET.fromstring(xml_text)
        ns = {"ietf-if": IETF_IF_NS, "ietf-ip": IETF_IP_NS}
        
        iface = None
        for cand in root.findall(".//ietf-if:interface", ns):
            if (cand.findtext("ietf-if:name", default="", namespaces=ns) or "").strip() == interface_name:
                iface = cand
                break
        if iface is None:
            iface = root.find(".//ietf-if:interface", ns)

        if iface is None:
            return {"status": "ok", "result": "not_found", "interface": None}
        
        name = iface.findtext("ietf-if:name", default=interface_name, namespaces=ns)
        description = iface.findtext("ietf-if:description", default=None, namespaces=ns)
        enabled_text = iface.findtext("ietf-if:enabled", default="true", namespaces=ns)
        admin_state = "up" if enabled_text.lower() == "true" else "down"
        ipv4 = None
        ip = iface.findtext(".//ietf-ip:address/ietf-ip:ip", default=None, namespaces=ns)
        netmask = iface.findtext(".//ietf-ip:address/ietf-ip:netmask", default=None, namespaces=ns) or iface.findtext(".//ietf-ip:address/ietf-ip:prefix-length", default=None, namespaces=ns)

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
    except Exception as e:
        return _handle_error(e)

def plan_interface(
    router,
    desired_interface,
    netconf_get_config=None,
):
    """Return create/update/no_change plan using NETCONF status."""
    return generic_plan_interface(
        router,
        desired_interface,
        lambda r, name: get_interface_state(r, name, netconf_get_config=netconf_get_config),
    )

def apply_interface(
    router,
    desired_interface,
    netconf_edit_config=None,
):
    """Apply complete desired interface state using NETCONF."""
    name = desired_interface["name"]
    number = name[len("Loopback"):].strip()
    ip_obj = IPv4Interface(desired_interface["ipv4"])
    ip_addr = str(ip_obj.ip)
    mask = str(ip_obj.network.netmask)
    desc = escape(desired_interface["description"])
    shutdown_xml = "\n        <shutdown/>" if desired_interface.get("admin_state") == "down" else ""
    config_xml = f"""<config xmlns="{NETCONF_NS}" xmlns:nc="{NETCONF_NS}">
  <native xmlns="{NATIVE_NS}">
    <interface>
      <Loopback nc:operation="replace">
        <name>{number}</name>
        <description>{desc}</description>
        <ip>
          <address>
            <primary>
              <address>{ip_addr}</address>
              <mask>{mask}</mask>
            </primary>
          </address>
        </ip>{shutdown_xml}
      </Loopback>
    </interface>
  </native>
</config>"""

    try:
        if netconf_edit_config is not None:
            netconf_edit_config(router, config_xml)
        else:
            with _connect(router) as m:
                m.edit_config(target="running", config=config_xml)

        return {"status": "ok", "result": "applied"}

    except Exception as e:
        return _handle_error(e)
