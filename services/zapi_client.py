# -*- coding: utf-8 -*-
# services/zapi_client.py
from __future__ import annotations

import os
import requests
from typing import Optional, Dict, Any

ZAPI_BASE = os.getenv("ZAPI_BASE", "").rstrip("/")
ZAPI_SENDTEXT_PATH = os.getenv("ZAPI_SENDTEXT_PATH", "/message/sendText")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "")  # se sua Z-API usar token em header
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE", "")
ZAPI_CLIENT = os.getenv("ZAPI_CLIENT_TOKEN")  # opcional, algumas contas exigem Client-Token header
ZAPI_TIMEOUT = float(os.getenv("ZAPI_TIMEOUT", "15"))
ZAPI_TRY_ALIASES = os.getenv("ZAPI_TRY_ALIASES", "false").lower() in ("1", "true", "yes")

def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if ZAPI_TOKEN:
        # ajuste a chave do header conforme seu provedor (Bearer, X-API-KEY, etc.)
        h["Authorization"] = f"Bearer {ZAPI_TOKEN}"
    # Algumas contas Z-API exigem um header 'Client-Token' em vez de Authorization
    if ZAPI_CLIENT:
        h["Client-Token"] = ZAPI_CLIENT
    return h

def send_text_to(*, phone: Optional[str] = None, group: Optional[str] = None, message: str) -> bool:
    """
    Envia texto para telefone OU grupo.
    Retorna True se 2xx, False caso contrário.
    """
    if not (ZAPI_BASE and message and message.strip()):
        return False

    # Build the candidate send endpoints. Use the configured path first.
    candidate_paths = [ZAPI_SENDTEXT_PATH]
    # Only add aliases when explicitly enabled (avoid extra outbound calls in production)
    if ZAPI_TRY_ALIASES:
        aliases = ["/send-text", "/message/sendText", "/message/send", "/sendText", "/sendMessage", "/v1/message/send"]
        for a in aliases:
            if a not in candidate_paths:
                candidate_paths.append(a)

    # construct candidate URLs (instance-based first if available)
    urls = []
    if ZAPI_INSTANCE and ZAPI_TOKEN:
        for p in candidate_paths:
            urls.append(f"{ZAPI_BASE}/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}{p}")
    for p in candidate_paths:
        urls.append(f"{ZAPI_BASE}{p}")

    payload: Dict[str, Any] = {"message": message}
    if group:
        payload = {"group": group.strip(), "message": message}
    elif phone:
        payload = {"phone": phone.strip(), "message": message}
    else:
        return False

    # Try each URL with both header strategies: headers from _headers() and no-auth (some instances expect token only in URL)
    tried = []
    for url in urls:
        for hdrs in (_headers(), {}):
            try:
                print(f">> ZAPI: POST {url} headers={[k+':'+v for k,v in hdrs.items()]} payload_keys={list(payload.keys())}", flush=True)
                r = requests.post(url, json=payload, headers=hdrs or None, timeout=ZAPI_TIMEOUT)
                text_snip = (r.text or "")[:1000]
                print(f">> ZAPI response: {r.status_code} {text_snip}", flush=True)
                j = None
                try:
                    j = r.json()
                except Exception:
                    j = None

                # treat body-level 'error' as failure
                if isinstance(j, dict) and j.get("error"):
                    print(f">> ZAPI provider error: {j.get('error')} - {j.get('message')}", flush=True)
                    tried.append((url, hdrs, r.status_code, j))
                    continue

                if 200 <= r.status_code < 300:
                    return True

                tried.append((url, hdrs, r.status_code, j or r.text))

            except Exception as e:
                print(f">> ZAPI request exception for {url}: {e}", flush=True)
                tried.append((url, hdrs, None, str(e)))

    # nothing worked
    print(
        ">> ZAPI: all attempts failed. Tried URLs:\n" + "\n".join([u for u in urls]),
        flush=True,
    )
    return False


# Note: Twilio fallback removed. This client now relies exclusively on the configured Z-API provider.

def send_text_from_row(row: Dict[str, Any], message: str) -> bool:
    """
    Conveniência: extrai destino do dict 'row' (in_group, group_id, telefone/from).
    """
    in_group = bool(row.get("in_group"))
    gid = str(row.get("group_id") or "").strip()
    phone = str(row.get("telefone") or row.get("from") or "").strip()

    if in_group and gid:
        print(f">> send_text_from_row: sending to group={gid} message={message[:80]!r}", flush=True)
        return send_text_to(group=gid, message=message)
    if phone:
        print(f">> send_text_from_row: sending to phone={phone} message={message[:80]!r}", flush=True)
        return send_text_to(phone=phone, message=message)
    return False
