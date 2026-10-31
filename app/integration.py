"""Part 4 student implementation."""

import yaml

from app.core import validate_request

from app.dispatcher import dispatch_request

from app.request_handler import validate_webex_envelope

def process_request(mentioned_people, attachment_path, bot_person_id):
    # ตรวจ Envelope ของ Webex
    envelope_error = validate_webex_envelope(mentioned_people, attachment_path, bot_person_id)
    if envelope_error is not None:
        return envelope_error
    
    # อ่านไฟล์ YAML
    try:
        with open(attachment_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {"status": "error", "result": "invalid_yaml"}

    # ตรวจสอบความถูกต้องของเนื้อหา YAML
    val_error = validate_request(data)
    if val_error.get("status") == "error":
        return val_error

    return dispatch_request(data)
