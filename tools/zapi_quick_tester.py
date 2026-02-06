#!/usr/bin/env python3
"""zapi_quick_tester.py

A focused tester that tries a small set of likely URL/payload/header variants
against your configured Z-API instance to verify whether a single test
message can be accepted.

Usage: run from project root with venv active:
    python tools/zapi_quick_tester.py

It reads ZAPI_* from .env and prints concise logs. It stops on first detected success.
"""
from __future__ import annotations
import os
import time
import requests
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ZAPI_BASE = (os.getenv("ZAPI_BASE") or "https://api.z-api.io").rstrip('/')
ZAPI_ID_INSTANCE = os.getenv("ZAPI_ID_INSTANCE", "").strip()
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()
ZAPI_SENDTEXT_PATH = os.getenv("ZAPI_SENDTEXT_PATH", "/message/sendText")
TIMEOUT = float(os.getenv("ZAPI_TIMEOUT", "12"))

PHONE_PLAIN = "5516992089829"
PHONE_PLUS = "+5516992089829"
PHONE_WHATSAPP = f"whatsapp:{PHONE_PLUS}"
PHONE_AT = f"{PHONE_PLAIN}@c.us"
MSG = f"Teste envio rápido - {time.strftime('%Y-%m-%d %H:%M:%S')}"

# try a focused set of paths (keep small)
PATHS = [ZAPI_SENDTEXT_PATH, "/message/send", "/sendText", "/sendMessage", "/v1/message/send"]

HEADERS_SETS = [
    ({"Authorization": f"Bearer {ZAPI_TOKEN}"}, 'Authorization: Bearer') if ZAPI_TOKEN else None,
    ({"Client-Token": ZAPI_CLIENT}, 'Client-Token') if ZAPI_CLIENT else None,
    ({}, 'no-auth'),
]
HEADERS_SETS = [h for h in HEADERS_SETS if h is not None]

# payloads: include several common field names and phone formats (plain, +prefix, whatsapp:, @c.us)
PAYLOADS = [
    ("json", {"phone": PHONE_PLAIN, "message": MSG}),
    ("json", {"phone": PHONE_PLUS, "message": MSG}),
    ("json", {"phone": PHONE_WHATSAPP, "message": MSG}),
    ("json", {"phone": PHONE_AT, "message": MSG}),
    ("json", {"to": PHONE_AT, "text": MSG}),
    ("json", {"to": PHONE_PLAIN, "text": MSG}),
    ("json", {"jid": PHONE_AT, "content": MSG}),
    ("json", {"jid": PHONE_AT, "message": MSG}),
    ("json", {"number": PHONE_PLAIN, "message": MSG}),
    ("json", {"number": PHONE_PLUS, "message": MSG}),
    ("json", {"chatId": PHONE_AT, "message": MSG}),
    ("json", {"destination": PHONE_AT, "message": MSG}),
]


def candidate_urls():
    urls = []
    if ZAPI_ID_INSTANCE and ZAPI_TOKEN:
        for p in PATHS:
            urls.append(f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}{p}")
    for p in PATHS:
        urls.append(f"{ZAPI_BASE}{p}")
    return list(dict.fromkeys(urls))


def is_success(r):
    if r is None:
        return False
    if not (200 <= r.status_code < 300):
        return False
    try:
        j = r.json()
    except Exception:
        j = None
    if isinstance(j, dict):
        if any(k.lower() == 'error' for k in j.keys()):
            return False
        if any(k.lower() in ('id', 'messageid', 'status', 'sent') for k in j.keys()):
            return True
        return True
    return True


def try_quick():
    urls = candidate_urls()
    attempts = 0
    print(f"Quick tester: {len(urls)} urls × {len(HEADERS_SETS)} headers × {len(PAYLOADS)} payloads")
    for url in urls:
        for hdr, hdr_name in HEADERS_SETS:
            for ptype, payload in PAYLOADS:
                attempts += 1
                print(f"Attempt #{attempts}: POST {url} header={hdr_name} payload_keys={list(payload.keys())}")
                try:
                    r = requests.post(url, json=payload, headers=hdr if hdr else {}, timeout=TIMEOUT)
                    text = (r.text or '')[:1000]
                    print(f"  => HTTP {r.status_code} | body: {text!r}")
                    if is_success(r):
                        print("*** SUCCESS DETECTED ***")
                        print(f"Successful details: url={url} header={hdr_name} payload={payload}")
                        try:
                            print("Response JSON:", r.json())
                        except Exception:
                            print("Response not JSON")
                        return True
                except Exception as e:
                    print(f"  => Exception: {e}")
                time.sleep(0.3)
    print("No success found in quick attempts")
    return False


if __name__ == '__main__':
    ok = try_quick()
    if ok:
        print("Quick tester finished: FOUND a working endpoint.")
    else:
        print("Quick tester finished: no working endpoint found.")
