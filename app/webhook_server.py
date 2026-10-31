"""Part 4 student implementation."""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import requests
from app.integration import process_request
from app.webex_client import WEBEX_API_BASE, WebexClient

class WebexEventHandler:
    def __init__(self, client, bot_person_id, processor=None):
        self.client = client
        self.bot_person_id = bot_person_id
        self.processor = processor or process_request

    def handle_event(self, event):
        if not isinstance(event, dict):
            return None

        if event.get("resource") != "messages" or event.get("event") != "created":
            return None

        data = event.get("data", {})
        message_id = data.get("id")
        if not message_id:
            return None

        # ตรวจสอบว่าคนส่งข้อความไม่ใช่ตัวบอตเอง
        if data.get("personId") == self.bot_person_id:
            return None
        message = self.client.get_message(message_id)

        # ตรวจสอบว่าคนส่งข้อความไม่ใช่ตัวบอตเองอีกครั้ง
        if message.get("personId") == self.bot_person_id:
            return None

        room_id = message.get("roomId")
        mentioned_people = message.get("mentionedPeople", [])
        files = message.get("files", [])

        # แนบหลายไฟล์
        if len(files) > 1:
            response = {"status": "error", "result": "multiple_attachments"}

        # ไม่แนบไฟล์
        elif len(files) == 0:
            response = self.processor(mentioned_people, None, self.bot_person_id)

        # แนบ 1 ไฟล์
        else:
            file_url = files[0]
            file_bytes = self.client.download_file(file_url)
            with TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / "request.yaml"
                temp_path.write_bytes(file_bytes)
                try:
                    response = self.processor(mentioned_people, temp_path, self.bot_person_id)
                finally:
                    if temp_path.exists():
                        temp_path.unlink()
        self.client.send_message(room_id, json.dumps(response))
        return response

def make_http_handler(submit_event):
    class WebhookHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "result": "healthy"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/webhook":
                length_hdr = self.headers.get("Content-Length")
                if not length_hdr or not length_hdr.isdigit():
                    self.send_error_response(400, "invalid_event")
                    return
                content_length = int(length_hdr)
                if content_length < 1 or content_length > 1_000_000:
                    self.send_error_response(400, "invalid_event")
                    return
                body = self.rfile.read(content_length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                    if not isinstance(payload, dict):
                        raise ValueError()
                except Exception:
                    self.send_error_response(400, "invalid_event")
                    return

                submit_event(payload)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "result": "accepted"}).encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

        def send_error_response(self, code, result):
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "error", "result": result}).encode("utf-8"))

        def log_message(self, format, *args):
            pass
    return WebhookHTTPHandler

def main():
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    token = os.getenv("WEBEX_BOT_TOKEN")
    client = None
    bot_person_id = None

    if token:
        try:
            client = WebexClient(token=token)
            res = requests.get(
                f"{WEBEX_API_BASE}/people/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if res.status_code == 200:
                bot_person_id = res.json().get("id")
        except Exception as e:
            logging.warning(f"Could not resolve bot identity: {e}")

    handler = WebexEventHandler(client, bot_person_id) if client and bot_person_id else None
    executor = ThreadPoolExecutor(max_workers=1)

    def submit_event(event):
        if handler:
            executor.submit(handler.handle_event, event)

    server = ThreadingHTTPServer((host, port), make_http_handler(submit_event))
    logging.info(f"Webhook server running on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        executor.shutdown(wait=False)

if __name__ == "__main__":
    main()
