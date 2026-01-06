# -*- coding: utf-8 -*-
# whatsapp_helpers.py — normalização de payloads Z-API + extração de texto

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # fallback compat
    ZoneInfo = None

# ----------------- utilitários internos -----------------

_DIGITS = re.compile(r"\D+")

def _only_digits(s: Optional[str]) -> Optional[str]:
    if not s or not isinstance(s, str):
        return None
    d = _DIGITS.sub("", s)
    return d or None

def _ms_to_iso(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(ms) / 1000.0, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None

def _iso_to_local(iso_utc: Optional[str], tzname: str = "America/Sao_Paulo") -> Optional[str]:
    if not iso_utc:
        return None
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        if ZoneInfo is None:
            return iso_utc
        return dt.astimezone(ZoneInfo(tzname)).isoformat()
    except Exception:
        return iso_utc

def _guess_is_group(phone_field: Optional[str], explicit_flag: Optional[bool]) -> bool:
    if explicit_flag is not None:
        return bool(explicit_flag)
    s = (phone_field or "").lower()
    return s.endswith("-group") or s.endswith("@g.us") or "group" in s

# ----------------- extração de texto -----------------

def _extract_text_from_payload(payload: dict) -> str:
    """
    Extrai texto relevante do payload do Z-API.
    Suporta text, audio, document, image — e retorna marcadores simbólicos claros para o modelo.
    """
    if not payload or not isinstance(payload, dict):
        return ""

    # Texto padrão Z-API
    t = payload.get("text")
    if isinstance(t, dict):
        msg = t.get("message") or t.get("caption")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

    # Texto direto
    if isinstance(payload.get("message"), str):
        return payload["message"].strip()

    # Mensagem aninhada
    if isinstance(payload.get("message"), dict):
        for k in ("text", "body", "message", "caption"):
            v = payload["message"].get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()

    # Outras chaves comuns
    for k in ("text", "body", "msg", "content"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # Mídias — transformadas em texto informativo (para o modelo saber interpretar)
    if isinstance(payload.get("audio"), dict):
        url = payload["audio"].get("audioUrl") or payload["audio"].get("url")
        if url:
            return f"[Áudio recebido: {url}]"

    if isinstance(payload.get("document"), dict):
        url = payload["document"].get("documentUrl") or payload["document"].get("url")
        if url:
            return f"[Documento recebido: {url}]"

    if isinstance(payload.get("image"), dict):
        url = payload["image"].get("imageUrl") or payload["image"].get("url")
        if url:
            return f"[Imagem recebida: {url}]"

    return "[Mensagem recebida, mas sem texto visível]"

# ----------------- dicionário normalizado -----------------

def _dict_merge(a: dict, b: dict) -> dict:
    """Mescla dois dicionários sem sobrescrever None."""
    res = dict(a or {})
    for k, v in (b or {}).items():
        if v is not None:
            res[k] = v
    return res

def parse_zapi_payload(p: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normaliza payloads do webhook Z-API.

    Retorna:
      {
        "text": str|None,
        "telefone": str|None,           # quem enviou (só dígitos)
        "raw_telefone": str|None,       # original
        "is_group": bool,
        "group_id": str|None,           # ex: "....-group"
        "group_name": str|None,         # chatName
        "sender_name": str|None,        # senderName
        "chat_phone": str|None,         # p["phone"] (id do chat)
        "connected_phone": str|None,    # p["connectedPhone"]
        "message_id": str|None,
        "instance_id": str|None,
        "timestamp_iso_utc": str|None,
        "timestamp_iso_sao_paulo": str|None
      }
    """
    if not isinstance(p, dict):
        p = {}

    text_val = _extract_text_from_payload(p)

    chat_phone = p.get("phone")
    connected_phone = p.get("connectedPhone") or p.get("connected_phone")
    is_group = _guess_is_group(chat_phone, p.get("isGroup"))

    raw_sender = (p.get("participantPhone") if is_group else (p.get("senderPhone") or chat_phone))
    if not raw_sender:
        raw_sender = p.get("from") or p.get("wa_id") or p.get("sender")
    telefone_digits = _only_digits(raw_sender)

    group_id = chat_phone if is_group else None
    group_name = p.get("chatName") or p.get("groupName") or None
    sender_name = p.get("senderName") or p.get("name") or None

    message_id = p.get("messageId") or p.get("id") or None
    instance_id = p.get("instanceId") or p.get("instance") or None

    ts_utc = _ms_to_iso(p.get("momment") or p.get("timestamp") or p.get("ts"))
    ts_sp = _iso_to_local(ts_utc, "America/Sao_Paulo") if ts_utc else None

    return {
        "text": text_val,
        "telefone": telefone_digits,
        "raw_telefone": raw_sender,
        "is_group": bool(is_group),
        "group_id": group_id,
        "group_name": group_name,
        "sender_name": sender_name,
        "chat_phone": chat_phone,
        "connected_phone": connected_phone,
        "message_id": message_id,
        "instance_id": instance_id,
        "timestamp_iso_utc": ts_utc,
        "timestamp_iso_sao_paulo": ts_sp,
    }
