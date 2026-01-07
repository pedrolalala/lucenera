from __future__ import annotations

"""Helpers around Supabase delivery_sessions / deliveries tables."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, cast

from supabase_client import supabase

Row = Dict[str, Any]
DELIVERY_SESSIONS_TABLE = os.getenv("DELIVERY_SESSIONS_TABLE", "delivery_sessions")
DELIVERIES_TABLE = os.getenv("DELIVERIES_TABLE", "deliveries")

logger = logging.getLogger("deliveries.supabase")

_SESSION_COLUMNS_CACHE: Optional[Set[str]] = None
_DELIVERIES_COLUMNS_CACHE: Optional[Set[str]] = None


def _as_row(value: Any) -> Optional[Row]:
    return cast(Row, value) if isinstance(value, dict) else None


def _data(resp: Any) -> Any:
    return getattr(resp, "data", None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits_only(value: Optional[str]) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _client(maybe_client=None):
    return maybe_client or supabase


def _session_columns(sb) -> Set[str]:
    global _SESSION_COLUMNS_CACHE
    if _SESSION_COLUMNS_CACHE is not None:
        return _SESSION_COLUMNS_CACHE

    columns: Set[str] = {
        "id",
        "entregador_phone",
        "step",
        "obra_codigo",
        "foto_media_id",
        "foto_path",
        "foto_url",
        "created_at",
        "updated_at",
        "finished_at",
    }
    if not sb:
        _SESSION_COLUMNS_CACHE = columns
        return columns
    try:
        resp = sb.table(DELIVERY_SESSIONS_TABLE).select("*").limit(1).execute()
        data = _data(resp)
        if isinstance(data, list) and data:
            columns.update(data[0].keys())
        elif isinstance(data, dict):
            columns.update(data.keys())
    except Exception:
        logger.warning(
            "SUPABASE_DELIVERY_ERROR action=discover_session_columns table=%s",
            DELIVERY_SESSIONS_TABLE,
        )
    _SESSION_COLUMNS_CACHE = columns
    return columns


def _deliveries_columns(sb) -> Set[str]:
    global _DELIVERIES_COLUMNS_CACHE
    if _DELIVERIES_COLUMNS_CACHE is not None:
        return _DELIVERIES_COLUMNS_CACHE

    columns: Set[str] = {
        "id",
        "obra_codigo",
        "entregador_phone",
        "recebedor_nome",
        "observacao",
        "foto_path",
        "foto_url",
        "itens_mencionados",
        "created_at",
    }
    if not sb:
        _DELIVERIES_COLUMNS_CACHE = columns
        return columns
    try:
        resp = sb.table(DELIVERIES_TABLE).select("*").limit(1).execute()
        data = _data(resp)
        if isinstance(data, list) and data:
            columns.update(data[0].keys())
        elif isinstance(data, dict):
            columns.update(data.keys())
    except Exception:
        logger.warning(
            "SUPABASE_DELIVERY_ERROR action=discover_deliveries_columns table=%s",
            DELIVERIES_TABLE,
        )
    _DELIVERIES_COLUMNS_CACHE = columns
    return columns


def get_open_delivery_session(entregador_phone: str, client=None) -> Optional[Row]:
    phone_key = _digits_only(entregador_phone)
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=get_open phone=%s",
        DELIVERY_SESSIONS_TABLE,
        phone_key or "-",
    )
    sb = _client(client)
    if not sb or not phone_key:
        logger.info("SUPABASE_DELIVERY_TABLE table=%s action=get_open skip", DELIVERY_SESSIONS_TABLE)
        return None
    try:
        resp = (
            sb.table(DELIVERY_SESSIONS_TABLE)
            .select("*")
            .eq("entregador_phone", phone_key)
            .is_("finished_at", None)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception(
            "SUPABASE_DELIVERY_ERROR action=get_open table=%s phone=%s",
            DELIVERY_SESSIONS_TABLE,
            phone_key,
        )
        raise

    data = _data(resp)
    row = None
    if isinstance(data, list) and data:
        row = _as_row(data[0])
    else:
        row = _as_row(data)
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=get_open result session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        (row or {}).get("id"),
    )
    return row


def create_delivery_session(entregador_phone: str, client=None, **extra) -> Row:
    phone_key = _digits_only(entregador_phone)
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=create_session phone=%s",
        DELIVERY_SESSIONS_TABLE,
        phone_key or "-",
    )
    sb = _client(client)
    if not sb or not phone_key:
        raise ValueError("entregador_phone inválido para criar sessão")
    session_columns = _session_columns(sb)
    now_iso = _now_iso()
    payload: Dict[str, Any] = {
        "entregador_phone": phone_key,
        "step": "AGUARDANDO_CODIGO",
        "created_at": now_iso,
        "updated_at": now_iso,
        **extra,
    }
    payload = {k: v for k, v in payload.items() if k in session_columns}
    try:
        resp = sb.table(DELIVERY_SESSIONS_TABLE).insert(payload).execute()
    except Exception:
        logger.exception(
            "SUPABASE_DELIVERY_ERROR action=create_session table=%s phone=%s",
            DELIVERY_SESSIONS_TABLE,
            phone_key,
        )
        raise
    inserted = _data(resp)
    row = None
    if isinstance(inserted, list) and inserted:
        row = _as_row(inserted[0])
    else:
        row = _as_row(inserted)
    row = row or payload
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=create_session result session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        row.get("id"),
    )
    return row


def update_delivery_session(session_id: Any, fields: Dict[str, Any], client=None) -> Row:
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=update_session session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        session_id,
    )
    sb = _client(client)
    if not sb or session_id is None:
        raise ValueError("session_id inválido para atualizar sessão")
    session_columns = _session_columns(sb)
    payload = {**(fields or {}), "updated_at": _now_iso()}
    payload = {k: v for k, v in payload.items() if k in session_columns}
    try:
        resp = (
            sb.table(DELIVERY_SESSIONS_TABLE)
            .update(payload)
            .eq("id", session_id)
            .execute()
        )
    except Exception:
        logger.exception(
            "SUPABASE_DELIVERY_ERROR action=update_session table=%s session_id=%s",
            DELIVERY_SESSIONS_TABLE,
            session_id,
        )
        raise
    updated = _data(resp)
    row = None
    if isinstance(updated, list) and updated:
        row = _as_row(updated[0])
    else:
        row = _as_row(updated)
    row = row or payload
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=update_session result session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        session_id,
    )
    return row


def finalize_delivery_session(session_id: Any, fields: Optional[Dict[str, Any]] = None, client=None) -> Row:
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=finalize_session session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        session_id,
    )
    sb = _client(client)
    if not sb or session_id is None:
        raise ValueError("session_id inválido para finalizar sessão")
    session_columns = _session_columns(sb)
    base = {**(fields or {})}
    now_iso = _now_iso()
    base.setdefault("step", "FINALIZADA")
    base["finished_at"] = now_iso
    base["updated_at"] = now_iso
    base = {k: v for k, v in base.items() if k in session_columns}
    try:
        resp = (
            sb.table(DELIVERY_SESSIONS_TABLE)
            .update(base)
            .eq("id", session_id)
            .execute()
        )
    except Exception:
        logger.exception(
            "SUPABASE_DELIVERY_ERROR action=finalize_session table=%s session_id=%s",
            DELIVERY_SESSIONS_TABLE,
            session_id,
        )
        raise
    data = _data(resp)
    row = None
    if isinstance(data, list) and data:
        row = _as_row(data[0])
    else:
        row = _as_row(data)
    row = row or base
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=finalize_session result session_id=%s",
        DELIVERY_SESSIONS_TABLE,
        session_id,
    )
    return row


def insert_delivery(payload: Dict[str, Any], client=None) -> Row:
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=insert_delivery obra=%s phone=%s",
        DELIVERIES_TABLE,
        payload.get("obra_codigo"),
        payload.get("entregador_phone"),
    )
    sb = _client(client)
    if not sb:
        raise ValueError("supabase client indisponível")
    delivery_columns = _deliveries_columns(sb)
    now_iso = _now_iso()
    insert_payload = {
        **payload,
        "created_at": payload.get("created_at") or now_iso,
    }
    insert_payload = {k: v for k, v in insert_payload.items() if k in delivery_columns}
    try:
        resp = sb.table(DELIVERIES_TABLE).insert(insert_payload).execute()
    except Exception:
        logger.exception(
            "SUPABASE_DELIVERY_ERROR action=insert_delivery table=%s obra=%s phone=%s",
            DELIVERIES_TABLE,
            payload.get("obra_codigo"),
            payload.get("entregador_phone"),
        )
        raise
    data = _data(resp)
    row = None
    if isinstance(data, list) and data:
        row = _as_row(data[0])
    else:
        row = _as_row(data)
    row = row or insert_payload
    logger.info(
        "SUPABASE_DELIVERY_TABLE table=%s action=insert_delivery result delivery_id=%s",
        DELIVERIES_TABLE,
        row.get("id"),
    )
    return row


def upload_to_storage(
    bucket: str,
    object_path: str,
    content_bytes: bytes,
    content_type: str,
    client=None,
) -> Dict[str, Any]:
    bytes_len = len(content_bytes) if content_bytes is not None else 0
    file_options = {
        "content-type": content_type or "application/octet-stream",
        "upsert": True,
    }
    logger.info(
        "DELIVERY_STORAGE_CALL bucket=%s path=%s bytes_len=%s upsert=%s",
        bucket,
        object_path,
        bytes_len,
        file_options.get("upsert"),
    )
    sb = _client(client)
    if not sb:
        error_msg = "Supabase client indisponível para upload"
        logger.error(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s error=%s",
            bucket,
            object_path,
            error_msg,
        )
        return {"ok": False, "error": error_msg, "raw": None}
    if not bucket or not object_path:
        error_msg = "Bucket e caminho são obrigatórios para upload"
        logger.error(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s error=%s",
            bucket,
            object_path,
            error_msg,
        )
        return {"ok": False, "error": error_msg, "raw": None}

    storage_client = sb.storage.from_(bucket)
    try:
        response = storage_client.upload(object_path, content_bytes, file_options=cast(Any, file_options))
    except Exception as exc:
        logger.exception(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s",
            bucket,
            object_path,
        )
        return {"ok": False, "error": str(exc), "raw": getattr(exc, "__dict__", None)}

    return {"ok": True, "error": None, "raw": response}


def upload_delivery_photo(
    bucket: str,
    object_path: str,
    content_bytes: bytes,
    content_type: str,
    client=None,
) -> Dict[str, Any]:
    logger.warning("upload_delivery_photo is deprecated; use upload_to_storage instead")
    return upload_to_storage(bucket, object_path, content_bytes, content_type, client=client)


def create_signed_url(bucket: str, object_path: str, expires_seconds: int, client=None) -> str:
    logger.info(
        "SUPABASE_STORAGE action=create_signed_url bucket=%s path=%s expires=%s",
        bucket,
        object_path,
        expires_seconds,
    )
    sb = _client(client)
    if not sb:
        raise ValueError("Supabase client indisponível para signed URL")
    storage_client = sb.storage.from_(bucket)
    try:
        response = storage_client.create_signed_url(object_path, expires_seconds)
    except Exception:
        logger.exception(
            "SUPABASE_STORAGE_ERROR action=create_signed_url bucket=%s path=%s",
            bucket,
            object_path,
        )
        raise
    if isinstance(response, dict):
        for key in ("signed_url", "signedUrl", "signedURL"):
            url = response.get(key)
            if isinstance(url, str) and url:
                return url
    signed_url = getattr(response, "get", lambda _key: None)("signed_url") if hasattr(response, "get") else None
    if isinstance(signed_url, str) and signed_url:
        return signed_url
    raise RuntimeError("Não foi possível obter signed URL do Supabase")


__all__ = [
    "DELIVERIES_TABLE",
    "DELIVERY_SESSIONS_TABLE",
    "create_delivery_session",
    "finalize_delivery_session",
    "get_open_delivery_session",
    "create_signed_url",
    "insert_delivery",
    "upload_to_storage",
    "upload_delivery_photo",
    "update_delivery_session",
]
