#!/usr/bin/env python3
"""zapi_bruteforce_tester.py

Tries a curated set of endpoint/method/header/payload variations against your Z-API
instance to discover a working combination for sending a text message.

Usage (from project root, inside your venv):
    python tools/zapi_bruteforce_tester.py

It reads configuration from `.env` (ZAPI_BASE, ZAPI_INSTANCE, ZAPI_TOKEN, ZAPI_CLIENT_TOKEN)
and writes results to `tools/zapi_tester.log`.

Note: This will make multiple HTTP requests to the provider. Keep the run short and
watch the output. Stop the script with Ctrl+C if you want to abort.
"""
from __future__ import annotations
import os
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

ZAPI_BASE = (os.getenv("ZAPI_BASE") or "https://api.z-api.io").rstrip('/')
ZAPI_ID_INSTANCE = os.getenv("ZAPI_ID_INSTANCE", "").strip()
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "").strip()
ZAPI_CLIENT = os.getenv("ZAPI_CLIENT_TOKEN", "").strip()

LOGFILE = BASE_DIR / "tools" / "zapi_tester.log"
LOGFILE.parent.mkdir(parents=True, exist_ok=True)

PHONE = os.getenv("TEST_PHONE", "5516992089829")
MSG = f"Teste bruteforce - {time.strftime('%Y-%m-%d %H:%M:%S')}"

PATHS = [
    "/message/sendText",
    "/message/send",
    "/sendText",
    "/sendMessage",
    "/message/sendMessage",
    "/messages",
    "/message",
    "/v1/message/sendText",
    "/v1/message/send",
    "/v1/sendText",
    "/api/message/sendText",
    "/api/sendMessage",
    # hyphenated variants (some deployments use hyphenated routes)
    "/message/send-text",
    "/send-text",
    "/message/send-text",
    "/api/send-text",
    "/v1/send-text",
    "/send_text",
]

# Additional HTTP methods to try (besides POST). GET is only used for 'query' payloads.
METHODS = ["POST", "PUT", "PATCH"]


def candidates_urls():
    urls = []
    # instance-based urls first (if available)
    if ZAPI_ID_INSTANCE and ZAPI_TOKEN:
        for p in PATHS:
            urls.append(f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}{p}")
            # try with /api prefix (some deployments use it)
            urls.append(f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}/api{p}")
    # base urls
    for p in PATHS:
        urls.append(f"{ZAPI_BASE}{p}")
        urls.append(f"{ZAPI_BASE}/api{p}")
    # small canonical variants
    urls.append(f"{ZAPI_BASE}/message")
    urls.append(f"{ZAPI_BASE}/messages")
    return list(dict.fromkeys(urls))


def header_sets():
    sets = []
    if ZAPI_CLIENT:
        sets.append(({"Client-Token": ZAPI_CLIENT}, "Client-Token"))
    if ZAPI_TOKEN:
        sets.append(({"Authorization": f"Bearer {ZAPI_TOKEN}"}, "Authorization"))
    sets.append(({}, "no-header"))
    return sets


def payload_variations():
    variations = []
    # common json bodies
    variations.append(("json", {"phone": PHONE, "message": MSG}))
    variations.append(("json", {"to": PHONE, "text": MSG}))
    variations.append(("json", {"number": PHONE, "message": MSG}))
    variations.append(("json", {"destination": PHONE, "message": MSG}))
    variations.append(("json", {"context": {"to": PHONE}, "text": MSG}))
    # form variations (application/x-www-form-urlencoded)
    variations.append(("form", {"phone": PHONE, "message": MSG}))
    variations.append(("form", {"to": PHONE, "text": MSG}))
    # query param: used only for GET
    variations.append(("query", {"phone": PHONE, "message": MSG}))
    return variations


def log(line: str):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    s = f"[{ts}] {line}\n"
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(s)
    print(s, end="")


def is_success_response(r: requests.Response, parsed=None) -> bool:
    # Consider success if HTTP 2xx and response body doesn't contain an 'error' key
    if r is None:
        return False
    if not (200 <= r.status_code < 300):
        return False
    if parsed is None:
        try:
            parsed = r.json()
        except Exception:
            parsed = None
    if isinstance(parsed, dict):
        # provider often returns {"error":...} on failures
        if any(k.lower() == 'error' for k in parsed.keys()):
            return False
        # if there's an 'id' or 'sent' or 'status' we accept
        if any(k.lower() in ('id', 'messageid', 'status', 'sent') for k in parsed.keys()):
            return True
        # otherwise, if dict but no explicit error key, treat as success
        return True
    # non-json 2xx (e.g., plain text) — treat as success
    return True


def try_all(max_attempts: int = 400, delay: float = 0.35):
    urls = candidates_urls()
    headers_list = header_sets()
    payloads = payload_variations()
    attempts = 0

    log(
        "Starting brute-force tester: "
        f"{len(urls)} urls × {len(headers_list)} headers × {len(payloads)} payloads ≈ "
        f"{len(urls)*len(headers_list)*len(payloads)} attempts (cap {max_attempts})"
    )

    for url in urls:
        for hdr, hdr_name in headers_list:
            for ptype, body in payloads:
                if attempts >= max_attempts:
                    log("Reached max attempts, stopping.")
                    return False

                # Decide which HTTP methods to try for this payload type
                methods_to_try = []
                if ptype == 'query':
                    methods_to_try = ['GET']
                else:
                    methods_to_try = METHODS

                for method in methods_to_try:
                    attempts += 1

                    data = None
                    json_body = None
                    params = None
                    content_type = None

                    if ptype == 'query':
                        params = body
                    elif ptype == 'form':
                        json_body = None
                        data = body
                        params = None
                        content_type = 'application/x-www-form-urlencoded'
                    else:
                        json_body = body
                        data = None
                        params = None
                        content_type = 'application/json'

                    # log start
                    log(f"Attempt #{attempts}: {method} {url} header={hdr_name} payload_type={ptype}")

                    try:
                        kwargs = dict(timeout=15)
                        if params is not None:
                            kwargs['params'] = params
                        if json_body is not None:
                            kwargs['json'] = json_body
                        if data is not None:
                            kwargs['data'] = data
                        if hdr:
                            kwargs['headers'] = hdr
                        # set content-type if form
                        if content_type and 'headers' in kwargs:
                            kwargs['headers'] = dict(kwargs.get('headers', {}))
                            kwargs['headers']['Content-Type'] = content_type

                        r = requests.request(method, url, **kwargs)
                        resp_text = r.text[:2000]
                        parsed = None
                        try:
                            parsed = r.json()
                        except Exception:
                            parsed = None

                        log(
                            f"  => HTTP {r.status_code} | parsed={bool(parsed)} | "
                            f"text={resp_text!r}"
                        )

                        if is_success_response(r, parsed):
                            log("*** SUCCESS DETECTED ***")
                            log(f"Successful attempt details: url={url} header={hdr_name} payload_type={ptype} method={method}")
                            if parsed is not None:
                                log(f"Response JSON: {json.dumps(parsed, ensure_ascii=False)}")
                            return True

                    except KeyboardInterrupt:
                        log("Aborted by user (KeyboardInterrupt)")
                        return False
                    except Exception as e:
                        log(f"  => Exception: {e}")

                    time.sleep(delay)

    log("Finished attempts: no success found")
    return False


if __name__ == '__main__':
    ok = try_all(max_attempts=600, delay=0.25)
    if ok:
        log("Brute-force tester finished: FOUND a working endpoint.")
    else:
        log("Brute-force tester finished: did not find a working endpoint.")
