from __future__ import annotations

"""Helpers around Supabase delivery_sessions / deliveries tables."""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Tuple, cast

from postgrest.exceptions import APIError

from supabase_client import ensure_env_loaded, get_supabase_client, get_supabase_key_source

Row = Dict[str, Any]

logger = logging.getLogger("deliveries.supabase")

ensure_env_loaded()
logger.info("SUPABASE_KEY_SOURCE source=%s", get_supabase_key_source() or "missing")

DELIVERY_SESSIONS_TABLE = os.getenv("DELIVERY_SESSIONS_TABLE", "delivery_sessions")
DELIVERIES_TABLE = os.getenv("DELIVERIES_TABLE", "deliveries")

_SESSION_COLUMNS_CACHE: Optional[Set[str]] = None
_DELIVERIES_COLUMNS_CACHE: Optional[Set[str]] = None
_REPORTED_SCHEMA_GAPS: Set[Tuple[str, str]] = set()


def _as_row(value: Any) -> Optional[Row]:
    return cast(Row, value) if isinstance(value, dict) else None


def _data(resp: Any) -> Any:
    return getattr(resp, "data", None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digits_only(value: Optional[str]) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _client(maybe_client=None):
    return maybe_client or get_supabase_client()


def _probe_optional_columns(sb, table: str, optional: Set[str]) -> Set[str]:
    available: Set[str] = set()
    missing: Set[str] = set()
    for col in optional:
        try:
            sb.table(table).select(col).limit(0).execute()
        except APIError as exc:  # coluna ausente no schema
            if getattr(exc, "code", "") in {"PGRST204", "42703"}:
                missing.add(col)
                continue
            logger.debug(
                "SUPABASE_SCHEMA_PROBE_FAIL table=%s column=%s code=%s", table, col, getattr(exc, "code", "?"),
            )
        except Exception:
            logger.exception("SUPABASE_SCHEMA_PROBE_EXCEPTION table=%s column=%s", table, col)
        else:
            available.add(col)
    for col in sorted(missing):
        key = (table, col)
        if key not in _REPORTED_SCHEMA_GAPS:
            logger.warning("SUPABASE_SCHEMA_MISSING table=%s column=%s", table, col)
            _REPORTED_SCHEMA_GAPS.add(key)
    return available


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
        "created_at",
        "updated_at",
        "finished_at",
    }
    optionals: Set[str] = {"recebedor_nome", "observacao", "foto_url"}
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
    if optionals:
        columns.update(_probe_optional_columns(sb, DELIVERY_SESSIONS_TABLE, optionals))
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
        "created_at",
    }
    optionals: Set[str] = {"foto_url", "itens_mencionados", "updated_at", "finished_at", "foto_media_id"}
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
    if optionals:
        columns.update(_probe_optional_columns(sb, DELIVERIES_TABLE, optionals))
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
    raw_path = str(object_path or "").strip().lstrip("/")
    bucket_prefix = f"{bucket.strip('/')}/" if bucket else ""
    while bucket_prefix and raw_path.startswith(bucket_prefix):
        raw_path = raw_path[len(bucket_prefix) :]
    normalized_path = raw_path

    bytes_len = len(content_bytes) if content_bytes is not None else 0
    file_options = {
        "content-type": content_type or "application/octet-stream",
        "upsert": "true",
    }
    logger.info(
        "DELIVERY_STORAGE_UPLOAD bucket=%s path=%s bytes_len=%s",
        bucket,
        normalized_path,
        bytes_len,
    )
    sb = _client(client)
    if not sb:
        error_msg = "Supabase client indisponível para upload"
        logger.error(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s error=%s",
            bucket,
            normalized_path,
            error_msg,
        )
        return {"ok": False, "error": error_msg, "raw": None}
    if not bucket or not object_path:
        error_msg = "Bucket e caminho são obrigatórios para upload"
        logger.error(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s error=%s",
            bucket,
            normalized_path,
            error_msg,
        )
        return {"ok": False, "error": error_msg, "raw": None}

    storage_client = sb.storage.from_(bucket)
    try:
        response = storage_client.upload(normalized_path, content_bytes, file_options=cast(Any, file_options))
    except Exception as exc:
        logger.exception(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s",
            bucket,
            normalized_path,
        )
        return {"ok": False, "error": str(exc), "raw": getattr(exc, "__dict__", None)}

    if isinstance(response, dict) and response.get("error"):
        error_detail = str(response.get("error"))
        logger.error(
            "SUPABASE_STORAGE_ERROR action=upload bucket=%s path=%s error=%s",
            bucket,
            normalized_path,
            error_detail,
        )
        return {"ok": False, "error": error_detail, "raw": response}

    logger.info(
        "DELIVERY_STORAGE_UPLOAD_OK bucket=%s path=%s",
        bucket,
        normalized_path,
    )
    return {"ok": True, "error": None, "raw": response, "path": normalized_path}


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
