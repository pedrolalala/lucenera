# -*- coding: utf-8 -*-
# services/zapi_client.py
from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Dict, Any, Tuple

import requests

ZAPI_BASE = os.getenv("ZAPI_BASE", "").rstrip("/")
ZAPI_SENDTEXT_PATH = os.getenv("ZAPI_SENDTEXT_PATH", "/message/sendText")
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN", "")  # se sua Z-API usar token em header
ZAPI_INSTANCE = os.getenv("ZAPI_INSTANCE", "")
ZAPI_CLIENT = os.getenv("ZAPI_CLIENT_TOKEN")  # opcional, algumas contas exigem Client-Token header
ZAPI_TIMEOUT = float(os.getenv("ZAPI_TIMEOUT", "15"))
ZAPI_TRY_ALIASES = os.getenv("ZAPI_TRY_ALIASES", "false").lower() in ("1", "true", "yes")

logger = logging.getLogger("zapi.client")

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


def enviar_mensagem_wa(*, telefone: Optional[str], mensagem: str) -> bool:
    """Envia mensagem de texto direto para um telefone via Z-API."""
    numero = (telefone or "").strip()
    if not numero:
        return False
    return send_text_to(phone=numero, message=mensagem)


def _media_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if ZAPI_TOKEN:
        headers["Authorization"] = f"Bearer {ZAPI_TOKEN}"
    if ZAPI_CLIENT:
        headers["Client-Token"] = ZAPI_CLIENT
    return headers


def _download_from_url(url: str) -> Tuple[bytes, str]:
    logger.info("ZAPI_MEDIA_DOWNLOAD url=%s", url)
    response = requests.get(url, timeout=ZAPI_TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    return response.content, content_type


def _download_media_from_id(media_id: str) -> Tuple[bytes, str]:
    if not (ZAPI_BASE and ZAPI_INSTANCE and ZAPI_TOKEN):
        raise RuntimeError("Z-API não configurada para download via media_id")

    candidate_paths = [
        f"/files/download/{media_id}",
        f"/files/{media_id}",
        f"/messages/download-file/{media_id}",
        f"/message/download-file/{media_id}",
        f"/media/download/{media_id}",
    ]
    last_error: Optional[Exception] = None
    for path in candidate_paths:
        url = f"{ZAPI_BASE}/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}{path}"
        try:
            logger.info("ZAPI_MEDIA_FETCH media_id=%s url=%s", media_id, url)
            response = requests.get(url, headers=_media_headers(), timeout=ZAPI_TIMEOUT)
        except Exception as exc:
            last_error = exc
            logger.warning("ZAPI_MEDIA_FETCH_FAIL media_id=%s url=%s error=%s", media_id, url, exc)
            continue

        if response.status_code != 200:
            logger.warning(
                "ZAPI_MEDIA_FETCH_HTTP_FAIL media_id=%s url=%s status=%s",
                media_id,
                url,
                response.status_code,
            )
            continue

        content_type = response.headers.get("Content-Type", "")
        lower_type = content_type.lower()
        if "application/json" in lower_type or "text/json" in lower_type:
            try:
                payload = response.json()
            except Exception as exc:
                last_error = exc
                logger.warning("ZAPI_MEDIA_FETCH_JSON_FAIL media_id=%s error=%s", media_id, exc)
                continue
            if isinstance(payload, dict):
                for key in ("url", "downloadUrl", "fileUrl", "mediaUrl"):
                    candidate = payload.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        return _download_from_url(candidate.strip())
                base64_data = payload.get("file") or payload.get("data") or payload.get("base64File")
                if isinstance(base64_data, str) and base64_data.strip():
                    try:
                        decoded = base64.b64decode(base64_data.strip(), validate=True)
                        return decoded, payload.get("contentType") or "application/octet-stream"
                    except Exception as exc:
                        last_error = exc
                        logger.warning("ZAPI_MEDIA_BASE64_FAIL media_id=%s error=%s", media_id, exc)
                        continue
            continue

        return response.content, content_type or "application/octet-stream"

    if last_error:
        raise RuntimeError(f"Falha ao baixar mídia via Z-API: {last_error}") from last_error
    raise RuntimeError("Falha ao baixar mídia via Z-API: nenhuma rota retornou sucesso")


def download_media_bytes(event: Dict[str, Any]) -> Tuple[bytes, str]:
    """Recebe dict contendo media_url ou media_id e retorna bytes + content-type."""

    if not event:
        raise ValueError("Payload vazio para download de mídia")

    if isinstance(event, str):
        return _download_from_url(event)

    media_url = None
    media_id = None

    if isinstance(event, dict):
        for key in ("media_url", "url", "download_url", "downloadUrl", "imageUrl", "fileUrl"):
            value = event.get(key)
            if isinstance(value, str) and value.strip():
                media_url = value.strip()
                break
        if not media_url:
            for key in ("media_id", "id", "mediaId", "file_id", "fileId", "mediaId"):
                value = event.get(key)
                if isinstance(value, str) and value.strip():
                    media_id = value.strip()
                    break

    if media_url:
        return _download_from_url(media_url)
    if media_id:
        return _download_media_from_id(media_id)

    raise ValueError("Payload não contém media_url ou media_id")
