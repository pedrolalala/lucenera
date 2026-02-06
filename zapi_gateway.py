# zapi_gateway.py
import os
import json
import logging
import requests

OUTGOING_ENABLED = os.getenv("OUTGOING_ENABLED", "false").lower() == "true"
ZAPI_BASE = os.getenv("ZAPI_BASE", "https://api.z-api.io")
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")

ZAPI_ID_INSTANCE = os.getenv('ZAPI_ID_INSTANCE')

def safe_send_text(phone: str, text: str) -> dict:
    """
    NUNCA envia se OUTGOING_ENABLED=false.
    Quando bloqueado, apenas loga o payload que *seria* enviado.
    """
    payload = {"phone": phone, "message": text}
    if not OUTGOING_ENABLED:
        logging.warning("[ZAPI BLOQUEADO] Envio suprimido. Payload: %s", json.dumps(payload, ensure_ascii=False))
        return {"ok": False, "blocked": True, "payload": payload}

    # Se (no futuro) você habilitar, aí sim dispara:
    url = f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()
    return {"ok": True, "blocked": False, "zapi_response": r.json()}
