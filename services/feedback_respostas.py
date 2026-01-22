"""Utilitários para armazenar e consultar feedbacks humanos das respostas do bot."""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from supabase_client import get_supabase_client

LOGGER = logging.getLogger("feedback.respostas")

_FEEDBACK_TABLE = "feedback_respostas"
_SELECT_COLUMNS = (
    "id,mensagem_cliente,contexto,resposta_bot_original,resposta_humana_correta,"\
    "categoria,intencao,telefone,origem,criada_em"
)


def _clean_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _prepare_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in {None, ""}}


def salvar_feedback_resposta(
    mensagem_cliente: str,
    resposta_bot_original: str,
    resposta_humana_correta: str,
    telefone: Optional[str] = None,
    origem: Optional[str] = None,
    *,
    categoria: Optional[str] = None,
    intencao: Optional[str] = None,
    contexto: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Salva um registro de feedback na tabela feedback_respostas."""
    mensagem = _clean_text(mensagem_cliente)
    resposta_bot = _clean_text(resposta_bot_original)
    resposta_humana = _clean_text(resposta_humana_correta)

    if not mensagem:
        raise ValueError("mensagem_cliente é obrigatório")
    if not resposta_humana:
        raise ValueError("resposta_humana_correta é obrigatório")

    payload = _prepare_payload(
        {
            "mensagem_cliente": mensagem,
            "contexto": _clean_text(contexto),
            "resposta_bot_original": resposta_bot,
            "resposta_humana_correta": resposta_humana,
            "telefone": _clean_text(telefone),
            "origem": _clean_text(origem),
            "categoria": _clean_text(categoria),
            "intencao": _clean_text(intencao),
        }
    )

    client = get_supabase_client()
    if client is None:
        LOGGER.warning("SUPABASE_UNAVAILABLE ao salvar feedback")
        return None

    try:
        response = client.table(_FEEDBACK_TABLE).insert(payload).execute()
    except Exception:  # pragma: no cover
        LOGGER.exception("SUPABASE_INSERT_FAIL feedback_respostas")
        return None

    data = response.data or []
    if not data:
        LOGGER.warning("SUPABASE_INSERT_NO_DATA feedback_respostas")
        return None

    row = data[0]
    if not isinstance(row, dict):
        LOGGER.warning("SUPABASE_INSERT_INVALID_ROW feedback_respostas tipo=%s", type(row).__name__)
        return None
    LOGGER.info(
        "FEEDBACK_RESPOSTA_SALVO id=%s telefone=%s intencao=%s categoria=%s",
        row.get("id"),
        payload.get("telefone"),
        payload.get("intencao"),
        payload.get("categoria"),
    )
    return row


def _extend_results(
    results: List[Dict[str, Any]],
    seen_ids: set,
    rows: Iterable[Any],
    limit: int,
) -> None:
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        rid = raw.get("id")
        if rid and rid in seen_ids:
            continue
        if rid:
            seen_ids.add(rid)
        results.append(raw)
        if len(results) >= limit:
            break


def buscar_feedbacks_para_contexto(
    intencao: Optional[str],
    categoria: Optional[str],
    *,
    limite: int = 5,
) -> List[Dict[str, Any]]:
    """Retorna até ``limite`` feedbacks relevantes para a intenção ou categoria informada."""
    desejado = max(1, min(int(limite or 1), 8))
    client = get_supabase_client()
    if client is None:
        LOGGER.warning("SUPABASE_UNAVAILABLE ao buscar feedbacks")
        return []

    queries: List[Any] = []
    if intencao:
        try:
            queries.append(
                client.table(_FEEDBACK_TABLE)
                .select(_SELECT_COLUMNS)
                .eq("intencao", _clean_text(intencao))
                .order("criada_em", desc=True)
                .limit(desejado)
            )
        except Exception:
            LOGGER.exception("SUPABASE_QUERY_FAIL feedback_respostas intencao")
    if categoria:
        try:
            queries.append(
                client.table(_FEEDBACK_TABLE)
                .select(_SELECT_COLUMNS)
                .eq("categoria", _clean_text(categoria))
                .order("criada_em", desc=True)
                .limit(desejado)
            )
        except Exception:
            LOGGER.exception("SUPABASE_QUERY_FAIL feedback_respostas categoria")

    try:
        queries.append(
            client.table(_FEEDBACK_TABLE)
            .select(_SELECT_COLUMNS)
            .order("criada_em", desc=True)
            .limit(desejado)
        )
    except Exception:
        LOGGER.exception("SUPABASE_QUERY_FAIL feedback_respostas fallback")
        return []

    results: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for query in queries:
        try:
            response = query.execute()
        except Exception:
            LOGGER.exception("SUPABASE_EXEC_FAIL feedback_respostas")
            continue
        rows = response.data or []
        if not isinstance(rows, Iterable):
            LOGGER.warning("SUPABASE_EXEC_INVALID_DATA feedback_respostas tipo=%s", type(rows).__name__)
            continue
        if not rows:
            continue
        prev_len = len(results)
        _extend_results(results, seen_ids, rows, desejado)
        if len(results) >= desejado:
            break
        if len(results) == prev_len:
            continue

    return results[:desejado]