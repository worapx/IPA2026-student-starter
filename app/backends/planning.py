from app.planner import build_plan

def plan_interface(
    router,
    desired_interface,
    get_interface_state,
):
    """Build a Part 2 plan from backend status."""
    interface_name = desired_interface["name"]
    
    # อ่านสถานะปัจจุบันผ่าน backend
    status_response = get_interface_state(router, interface_name)
    
    if status_response.get("status") == "error":
        return status_response

    # ดึงข้อมูล current interface (ถ้า not_found ให้เป็น None)
    if status_response.get("result") == "not_found":
        current_interface = None
    else:
        current_interface = status_response.get("interface")

    return build_plan(desired_interface, current_interface)