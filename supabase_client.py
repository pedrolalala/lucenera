# supabase_client.py — factory centralizado do client Supabase
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv

try:
    from supabase import Client, create_client
except Exception as exc:  # pragma: no cover - erro de dependência
    raise RuntimeError("Instale a lib: pip install 'supabase>=2.5.1'") from exc


_LOGGER = logging.getLogger("supabase.client")

_ENV_LOCK = threading.Lock()
_CLIENT_LOCK = threading.Lock()
_ENV_LOADED = False
_SUPABASE_URL: Optional[str] = None
_SUPABASE_KEY: Optional[str] = None
DEFAULT_TABLE = "mensagens"
DEFAULT_IDCOL = "id_num"
supabase: Optional[Client] = None  # compat legado; use get_supabase_client()


def _safe_prefix(value: Optional[str], length: int = 10) -> str:
    if not value:
        return "(missing)"
    clean = value.strip().strip('"').strip("'")
    return clean[:length]


def _clean_env(name: str) -> Optional[str]:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().strip('"').strip("'") or None


def ensure_env_loaded() -> None:
    global _ENV_LOADED, _SUPABASE_URL, _SUPABASE_KEY, DEFAULT_TABLE, DEFAULT_IDCOL
    if _ENV_LOADED:
        return
    with _ENV_LOCK:
        if _ENV_LOADED:
            return
        base_dir = Path(__file__).resolve().parent
        dotenv_path = find_dotenv()
        if dotenv_path:
            load_dotenv(dotenv_path)
        load_dotenv(base_dir / ".env")
        _SUPABASE_URL = _clean_env("SUPABASE_URL")
        key_a = _clean_env("SUPABASE_SERVICE_ROLE")
        key_b = _clean_env("SUPABASE_SERVICE_ROLE_KEY")
        _SUPABASE_KEY = key_a or key_b
        DEFAULT_TABLE = _clean_env("TABLE") or DEFAULT_TABLE
        DEFAULT_IDCOL = _clean_env("ID_COLUMN") or DEFAULT_IDCOL
        _ENV_LOADED = True
        _LOGGER.info(
            "SUPABASE_ENV_LOADED url_prefix=%s key_prefix=%s",
            _safe_prefix(_SUPABASE_URL, 24),
            _safe_prefix(_SUPABASE_KEY, 12),
        )


def _validate_config() -> None:
    ensure_env_loaded()
    if not _SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL não configurada. Defina no .env ou ambiente.")
    if not _SUPABASE_KEY:
        raise RuntimeError(
            "Chave Supabase ausente. Configure SUPABASE_SERVICE_ROLE ou SUPABASE_SERVICE_ROLE_KEY."
        )


def get_supabase_client(force_refresh: bool = False) -> Optional[Client]:
    global supabase
    ensure_env_loaded()
    if supabase and not force_refresh:
        return supabase
    with _CLIENT_LOCK:
        if supabase and not force_refresh:
            return supabase
        if force_refresh:
            supabase = None
        try:
            _validate_config()
        except RuntimeError as config_error:
            _LOGGER.error("SUPABASE_CLIENT_ERROR message=%s", config_error)
            return None
        try:
            supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - falhas externas
            _LOGGER.exception("SUPABASE_CLIENT_CREATE_FAIL")
            supabase = None
            return None
        _LOGGER.info(
            "SUPABASE_CLIENT_READY url_prefix=%s key_prefix=%s",
            _safe_prefix(_SUPABASE_URL, 24),
            _safe_prefix(_SUPABASE_KEY, 12),
        )
    return supabase


def require_supabase_client(force_refresh: bool = False) -> Client:
    client = get_supabase_client(force_refresh=force_refresh)
    if client is None:
        raise RuntimeError(
            "Supabase não configurado. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE ou SUPABASE_SERVICE_ROLE_KEY."
        )
    return client


def get_supabase() -> Optional[Client]:  # compatibilidade
    return get_supabase_client()


def require_supabase() -> Client:  # compatibilidade
    return require_supabase_client()


def table(name: Optional[str] = None):
    sb = require_supabase_client()
    ensure_env_loaded()
    tbl = (name or DEFAULT_TABLE).strip()
    return sb.table(tbl)


def column_exists(tbl: Optional[str], col: str) -> bool:
    try:
        _ = table(tbl).select(col).limit(0).execute()
        return True
    except Exception:
        return False


def table_exists(tbl: Optional[str] = None) -> bool:
    try:
        _ = table(tbl).select("*").limit(1).execute()
        return True
    except Exception:
        return False


def healthcheck(tbl: Optional[str] = None) -> dict:
    ensure_env_loaded()
    info = {
        "url_present": bool(_SUPABASE_URL),
        "key_present": bool(_SUPABASE_KEY),
        "client_created": supabase is not None,
        "table": (tbl or DEFAULT_TABLE),
        "table_exists": False,
        "id_column_exists": False,
        "note": "",
    }
    if supabase is None:
        info["note"] = "client não criado"
        return info
    t = info["table"]
    try:
        info["table_exists"] = table_exists(t)
        if info["table_exists"]:
            info["id_column_exists"] = column_exists(t, DEFAULT_IDCOL)
        else:
            info["note"] = "tabela não encontrada (ou nome diferente)"
    except Exception as exc:
        info["note"] = f"erro ao checar: {type(exc).__name__}: {exc}"
    return info


def supabase_diagnostics() -> dict:
    ensure_env_loaded()
    return {
        "url_present": bool(_SUPABASE_URL),
        "url_prefix": _safe_prefix(_SUPABASE_URL, 32),
        "key_present": bool(_SUPABASE_KEY),
        "key_prefix": _safe_prefix(_SUPABASE_KEY, 12),
    }
