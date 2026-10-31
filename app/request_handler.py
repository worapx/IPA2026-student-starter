from app.core import process_request_file

def validate_webex_envelope(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    Validate the target bot's actual mention and YAML attachment.
    Return an error response, or None when the envelope is valid.
    """
    # ตรวจสอบว่า bot_person_id มีค่า และ mentioned_people เป็น list ที่มี bot_person_id อยู่จริง
    if not bot_person_id or not isinstance(mentioned_people, list) or bot_person_id not in mentioned_people:
        return {"status": "error", "result": "missing_bot_mention"}

    # ตรวจสอบว่ามีไฟล์แนบหรือไม่
    if attachment_path is None:
        return {"status": "error", "result": "no_yaml"}

    return None

def handle_webex_request(
    mentioned_people,
    attachment_path,
    bot_person_id,
):
    """
    Validate the envelope, then validate the attached YAML request.
    Return a response dictionary. Do not dispatch to a router.
    """
    # ตรวจสอบ envelope ก่อน
    envelope_error = validate_webex_envelope(
        mentioned_people,
        attachment_path,
        bot_person_id,
    )
    if envelope_error is not None:
        return envelope_error

    # นำไฟล์แนบไป validate ต่อด้วย core
    return process_request_file(attachment_path)