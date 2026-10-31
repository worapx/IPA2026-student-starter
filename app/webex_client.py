"""Part 4 student implementation."""

import os
import requests

WEBEX_API_BASE = 'https://webexapis.com/v1'

class WebexClient:
    def __init__(self, token=None, session=None):
        self.token = token or os.getenv("WEBEX_BOT_TOKEN")
        if not self.token:
            raise PermissionError("WEBEX_BOT_TOKEN is required")
        self.session = session or requests.Session()

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
        }

    def get_message(self, message_id):
        url = f"{WEBEX_API_BASE}/messages/{message_id}"
        res = self.session.get(url, headers=self.headers, timeout=10)
        res.raise_for_status()
        return res.json()

    def download_file(self, file_url):
        headers = {"Authorization": f"Bearer {self.token}"}
        res = self.session.get(file_url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.content

    def send_message(self, room_id, text):
        url = f"{WEBEX_API_BASE}/messages"
        payload = {"roomId": room_id, "text": text}
        res = self.session.post(url, headers=self.headers, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()
