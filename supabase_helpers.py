"""Supabase helper utilities shared across the project."""
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from supabase_client import get_supabase_client
from notificacoes.teams_alerta import enviar_falha_para_teams

TABLE = "mensagens"
ID_COLUMN = "id"
FAILURES_TABLE = os.getenv("FAILURES_TABLE") or "falhas_processamento"

_HELPER_LOG = logging.getLogger("supabase.helpers")

def _sb_insert(payload: dict) -> Optional[dict]:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        data = {k: v for k, v in payload.items() if v is not None}
        resp = supabase.table(TABLE).insert(data).execute()
        result = (resp.data or [None])[0]
        return result if isinstance(result, dict) else None
    except Exception as e:
        print(">> Supabase insert erro:", e)
        return None

def _sb_update(id_val, fields: dict) -> Optional[dict]:
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        data = {k: v for k, v in fields.items() if v is not None}
        resp = supabase.table(TABLE).update(data).eq(ID_COLUMN, id_val).execute()
        if resp.data:
            result = resp.data[0]
            return result if isinstance(result, dict) else None
    except Exception as e:
        print(f">> Supabase update erro (col={ID_COLUMN}):", e)
    return None

def _get_row_id(row: dict):
    if not row:
        return None
    return row.get(ID_COLUMN) or row.get("id")


def log_processing_failure(
    message_id: Any,
    *,
    telefone: Optional[str] = None,
    mensagem: Optional[str] = None,
    erro: Optional[str] = None,
) -> bool:
    """Persist a critical processing failure into Supabase when possible."""
    supabase = get_supabase_client()
    if not supabase:
        _HELPER_LOG.warning(
            "FAILURE_LOG_SKIP message_id=%s motivo=supabase_unavailable",
            message_id,
        )
        return False

    payload = {
        "id_mensagem": message_id,
        "telefone": telefone,
        "mensagem": mensagem,
        "erro": erro,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    clean_payload = {k: v for k, v in payload.items() if v is not None}
    try:
        supabase.table(FAILURES_TABLE).insert(clean_payload).execute()
        return True
    except Exception as exc:
        _HELPER_LOG.warning(
            "FAILURE_LOG_INSERT_FAIL message_id=%s err=%s",
            message_id,
            exc,
        )
        return False


def registrar_falha(
    message_id: Any,
    *,
    motivo: Optional[str] = None,
    telefone: Optional[str] = None,
    mensagem: Optional[str] = None,
) -> bool:
    """Alias semântico para log_processing_failure."""
    result = log_processing_failure(
        message_id,
        telefone=telefone,
        mensagem=mensagem,
        erro=motivo,
    )
    try:
        enviar_falha_para_teams(
            telefone=telefone or "desconhecido",
            mensagem=mensagem or "",
            erro=motivo or "Falha sem detalhe",
            mensagem_id=message_id,
        )
    except Exception as exc:
        _HELPER_LOG.warning(
            "TEAMS_FALHA_ALERT_SEND_FAIL message_id=%s err=%s",
            message_id,
            exc,
        )
    return result