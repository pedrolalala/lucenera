"""Integração dedicada ao armazenamento e consulta de entregas no Supabase."""
from __future__ import annotations

import datetime as _dt
import logging
import os
from typing import Any, Dict, List, Optional, TypeAlias, Union, cast

from services.teams_parser import ParsedEntrega

from supabase_client import get_supabase_client

LOGGER = logging.getLogger(__name__)

_DEFAULT_TABLE = os.getenv("SUPABASE_ENTREGAS_TABLE", "entregas_logistica")
_TEAMS_TABLE = os.getenv("SUPABASE_ENTREGAS_TEAMS_TABLE", "entregas_teams")

JSONPrimitive = Union[str, int, float, bool, None]
JSON: TypeAlias = Union[JSONPrimitive, Dict[str, "JSON"], List["JSON"]]
JSONDict: TypeAlias = Dict[str, JSON]


def _client():
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client is not configured")
    return client


def salvar_entrega(payload: Dict[str, Any], *, table: Optional[str] = None) -> Dict[str, Any]:
    """Persiste os dados da entrega e retorna o registro criado."""

    supabase = _client()
    tabela = table or _DEFAULT_TABLE
    json_payload = cast(JSONDict, payload)
    response = supabase.table(tabela).insert(json_payload).execute()
    error = getattr(response, "error", None)
    if error:
        LOGGER.error("Erro ao salvar entrega no Supabase: %s", error)
        raise RuntimeError(str(error))
    if response.data:
        return cast(Dict[str, Any], response.data[0])
    return payload


def listar_entregas_por_data(data: _dt.date, *, table: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna entregas de uma data específica."""

    supabase = _client()
    tabela = table or _DEFAULT_TABLE
    response = (
        supabase.table(tabela)
        .select("*")
        .eq("data", data.isoformat())
        .order("created_at", desc=False)
        .execute()
    )
    error = getattr(response, "error", None)
    if error:
        LOGGER.error("Erro ao consultar entregas por data: %s", error)
        return []
    return cast(List[Dict[str, Any]], response.data or [])


def atualizar_status_entrega(
    entrega_id: Any, status: str, *, table: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Permite atualização futura de status manual."""

    supabase = _client()
    tabela = table or _DEFAULT_TABLE
    response = (
        supabase.table(tabela)
        .update({"status": status})
        .eq("id", entrega_id)
        .execute()
    )
    error = getattr(response, "error", None)
    if error:
        LOGGER.error("Erro ao atualizar status: %s", error)
        return None
    if response.data:
        return cast(Dict[str, Any], response.data[0])
    return None


def listar_statuses(*, table: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retorna lista resumida de entregas com status."""

    supabase = _client()
    tabela = table or _DEFAULT_TABLE
    response = supabase.table(tabela).select("id, cliente, status, data").execute()
    error = getattr(response, "error", None)
    if error:
        LOGGER.error("Erro ao consultar status de entregas: %s", error)
        return []
    return cast(List[Dict[str, Any]], response.data or [])


def registrar_entrega(parsed: ParsedEntrega, *, table: Optional[str] = None) -> Dict[str, Any]:
    """Salva entrega originada do Teams na tabela dedicada."""

    supabase = _client()
    tabela = table or _TEAMS_TABLE
    payload = parsed.to_record()
    payload.update(
        {
            "data_recebida": _dt.datetime.utcnow().isoformat(),
            "status": "pendente",
        }
    )

    json_payload = cast(JSONDict, payload)
    response = supabase.table(tabela).insert(json_payload).execute()
    error = getattr(response, "error", None)
    if error:
        LOGGER.error("Erro ao registrar entrega do Teams: %s", error)
        raise RuntimeError(str(error))
    if response.data:
        return cast(Dict[str, Any], response.data[0])
    return payload


__all__ = [
    "salvar_entrega",
    "listar_entregas_por_data",
    "atualizar_status_entrega",
    "listar_statuses",
    "registrar_entrega",
]
