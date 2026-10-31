MANAGED_FIELDS = ("ipv4", "description", "admin_state")

def build_plan(desired_interface, current_interface):
    """
    Compare desired interface state with normalized current state
    and return a plan according to specs/plan-spec-v1.md.
    """
    # กรณีที่ไม่มี Interface อยู่เลย -> create
    if current_interface is None:
        changes = {
            field: {"to": desired_interface[field]}
            for field in MANAGED_FIELDS
            if field in desired_interface
        }
        return {
            "status": "ok",
            "result": "planned",
            "operation": "create",
            "changes": changes,
        }

    # กรณีที่มี Interface อยู่แล้ว -> เปรียบเทียบทีละฟิลด์
    changes = {}
    for field in MANAGED_FIELDS:
        desired_val = desired_interface.get(field)
        current_val = current_interface.get(field)
        
        # ถ้าค่าไม่ตรงกัน ให้บันทึกการเปลี่ยนแปลง from -> to
        if desired_val != current_val:
            changes[field] = {
                "from": current_val,
                "to": desired_val,
            }

    # ถ้ามีฟิลด์ที่ต่างกัน -> update
    if changes:
        return {
            "status": "ok",
            "result": "planned",
            "operation": "update",
            "changes": changes,
        }

    # ถ้าค่าตรงกันทุกฟิลด์ -> no_change
    return {
        "status": "ok",
        "result": "planned",
        "operation": "no_change",
        "changes": {},
    }