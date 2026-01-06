"""Máquina de estados para o fluxo especial de entregas.

Este módulo NÃO envia mensagens nem notifica o Teams. Ele apenas
administra o estado das entregas na tabela `entregas` e informa ao caller
qual resposta enviar ao WhatsApp, além do payload final quando a entrega é
concluída.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, List

from supabase_helpers import supabase

ENTREGADORES = {
    "5516992089829",  # número de teste
}

JSONDict = Dict[str, Any]

ENTREGAS_TABLE = "entregas"
_STATUS_EM_ANDAMENTO = {
    "coletando_endereco",
    "coletando_foto",
    "coletando_observacao",
}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_phone(value: Optional[str]) -> str:
    digits = [ch for ch in str(value or "") if ch.isdigit()]
    return "".join(digits)


def is_entregador(telefone: str) -> bool:
    """Retorna True se o telefone estiver na lista de entregadores."""
    normalized = _normalize_phone(telefone)
    result = normalized in ENTREGADORES
    print(
        "[DEBUG ENTREGAS] is_entregador telefone_normalizado:",
        normalized,
        "autorizado?",
        result,
        flush=True,
    )
    return result


def _get_row_id(row: Dict) -> Optional[str]:
    for key in ("id", "id_num", "message_trigger_id"):
        val = row.get(key)
        if val is not None:
            return str(val)
    return None


def _strip_outer_quotes(value: str) -> str:
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        return value[1:-1]
    if value.startswith("'") and value.endswith("'") and len(value) >= 2:
        return value[1:-1]
    return value


def _get_nome_entregador(row: Dict) -> Optional[str]:
    raw = row.get("nome")
    if not isinstance(raw, str):
        return None
    nome = _strip_outer_quotes(raw.strip())
    return nome or None


def _get_message_text(row: Dict) -> str:
    raw = row.get("mensagem")
    if not isinstance(raw, str):
        return ""
    text = raw.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    return text


def _get_sessao_ativa(telefone: str) -> Optional[Dict]:
    if not supabase:
        return None
    tel_norm = _normalize_phone(telefone)
    try:
        resp = (
            supabase.table(ENTREGAS_TABLE)
            .select("*")
            .eq("telefone", tel_norm)
            .in_("status", list(_STATUS_EM_ANDAMENTO))
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # pragma: no cover - telemetria
        print(f">> entregas_flow: erro ao buscar sessão ativa: {exc}")
        return None
    data = resp.data or []
    return data[0] if data and isinstance(data[0], dict) else None


def _criar_sessao_entrega(row: Dict) -> Optional[JSONDict]:
    if not supabase:
        return None
    telefone = _normalize_phone(row.get("telefone"))
    if not telefone:
        return None
    payload = {
        "telefone": telefone,
        "nome_entregador": _get_nome_entregador(row),
        "status": "coletando_endereco",
        "mensagem_trigger_id": _get_row_id(row),
        "created_at": _now_utc_iso(),
        "updated_at": _now_utc_iso(),
    }
    try:
        resp = supabase.table(ENTREGAS_TABLE).insert(payload).execute()
        data = resp.data or []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]  # type: ignore[return-value]
        return None
    except Exception as exc:  # pragma: no cover - telemetria
        print(f">> entregas_flow: erro ao criar sessão: {exc}")
        return None


def _atualizar_sessao_entrega(entrega_id: str, campos: Dict) -> Optional[JSONDict]:
    if not supabase:
        return None
    campos = {**campos, "updated_at": _now_utc_iso()}
    try:
        resp = (
            supabase.table(ENTREGAS_TABLE)
            .update(campos)
            .eq("id", entrega_id)
            .execute()
        )
        data = resp.data or []
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return data[0]  # type: ignore[return-value]
        return None
    except Exception as exc:  # pragma: no cover - telemetria
        print(f">> entregas_flow: erro ao atualizar sessão: {exc}")
        return None


def _extrair_endereco_codigo(texto: str) -> Tuple[str, Optional[str]]:
    if not texto:
        return "", None
    texto_norm = texto.strip()
    lower = texto_norm.lower()
    for marcador in ("codigo da obra", "código da obra", "codigo", "código"):
        idx = lower.find(marcador)
        if idx >= 0:
            prefixo = texto_norm[:idx].strip().strip(",;:- ")
            resto = texto_norm[idx + len(marcador):].strip()
            partes = resto.split()
            codigo = partes[0].strip("#-,:.; ") if partes else ""
            codigo = codigo or None
            return prefixo, codigo
    return texto_norm, None


def _detectar_imagem(row: Dict) -> Optional[str]:
    for key in ("media_url", "download_url", "foto_url", "image_url"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    # TODO: integrar com o formato real de mídia quando o payload for definido pela Z-API.
    return None


def _normalizar_gatilho(texto: str) -> str:
    if not texto:
        return ""
    t = texto.strip()
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    t = t.lower()
    t = " ".join(t.split())
    return t


def handle_entregas_message(row: Dict) -> Tuple[Optional[str], Optional[Dict]]:
    print(
        "[DEBUG ENTREGAS] handle_entregas_message row.telefone=",
        row.get("telefone"),
        "mensagem=",
        row.get("mensagem"),
        flush=True,
    )
    telefone = row.get("telefone")
    if not telefone or not is_entregador(telefone):
        return None, None

    texto_original = _get_message_text(row)
    texto_norm = _normalizar_gatilho(texto_original)

    sessao = _get_sessao_ativa(telefone)

    if not sessao:
        print(
            "[DEBUG ENTREGAS] criando sessao para entregador:",
            _normalize_phone(telefone),
            "texto_norm:",
            texto_norm,
            flush=True,
        )
        sessao = _criar_sessao_entrega(row)
        if not sessao:
            return None, None
        reply = (
            "Entrega registrada ✅\n\n"
            "Qual o endereço e o código da obra?\n"
            "Exemplo: Condomínio Quinta da Alvorada 522, código 25380."
        )
        return reply, sessao

    status = (sessao.get("status") or "").strip().lower()
    entrega_id = sessao.get("id")
    if not entrega_id:
        return None, None

    if status == "coletando_endereco":
        endereco, codigo = _extrair_endereco_codigo(texto_norm)
        campos = {"status": "coletando_foto", "endereco": endereco}
        if codigo:
            campos["codigo_obra"] = codigo
        sessao = _atualizar_sessao_entrega(entrega_id, campos) or sessao
        reply = "Perfeito! Me manda a foto da entrega, por favor."
        return reply, None

    if status == "coletando_foto":
        foto_url = _detectar_imagem(row)
        if not foto_url:
            reply = "Não encontrei a foto. Pode reenviar a imagem da entrega, por favor?"
            return reply, None
        sessao = _atualizar_sessao_entrega(
            entrega_id,
            {"status": "coletando_observacao", "foto_url": foto_url},
        ) or sessao
        reply = (
            "Foto recebida! Alguma observação sobre a entrega?\n"
            "Se não tiver, pode responder \"sem observações\"."
        )
        return reply, sessao

    if status == "coletando_observacao":
        observacao = texto_norm or "sem observações"
        sessao = _atualizar_sessao_entrega(
            entrega_id,
            {"status": "concluida", "observacao": observacao},
        ) or sessao
        reply = "Entrega registrada ✅\nObrigado! Qualquer problema é só avisar."
        return reply, sessao

    return None, None


# Exemplo de entrega_finalizada:
# {
#   "endereco": "Condomínio Quinta da Alvorada 522",
#   "codigo_obra": "25380",
#   "telefone": "5516992089829",
#   "nome_entregador": "Pedro",
#   "foto_url": "https://...",
#   "observacao": "faltaram 5 unidades",
# }
