# supabase_repo.py
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from supabase_client import get_supabase_client

TABLE = "whatsapp_messages"

def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def save_inbound_message(
    telefone: str,
    texto: Optional[str],
    *,
    data: Optional[datetime] = None,
    group_id: Optional[str] = None,
    group_name: Optional[str] = None,
    nome_display: Optional[str] = None,
    raw: Optional[dict] = None,
    status: str = "received",
    ai_draft: Optional[str] = None,
    approval_mode: bool = False,
    used_ai: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Insere uma linha de mensagem recebida, compatível com o app.py.
    Retorna o registro criado.
    """
    when = _iso(data or datetime.now(timezone.utc))
    payload = {
        "telefone": telefone,
        "mensagem": {"text": texto or "", "raw": raw} if (raw is not None) else {"text": texto or ""},
        "nome": {"display": nome_display} if nome_display else None,
        "data": when,
        "group_id": group_id,
        "group_name": group_name,
        "ai_draft": ai_draft,
        "used_ai": bool(ai_draft) if used_ai is None else used_ai,
        "approval_mode": bool(approval_mode),
        "status": status,
    }
    # remove chaves None para não conflitar com políticas
    payload = {k: v for k, v in payload.items() if v is not None}
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase indisponível para salvar mensagem inbound")
    resp = client.table(TABLE).insert(payload).execute()
    return (resp.data or [None])[0]

def save_outbound_result(row_id, final_out: str, sent: bool, *, error: Optional[str] = None, approval_mode: bool = False):
    """
    Atualiza a linha com a saída final (igual ao que seu app.py faz no fluxo normal).
    """
    status_val = "sent" if sent else ("awaiting_approval" if approval_mode else "error")
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase indisponível para atualizar mensagem outbound")
    resp = (client.table(TABLE)
            .update({
                "final_out": final_out,
                "used_ai": True,
                "status": status_val,
                "error": error,
                "approved": True if sent or approval_mode else None,
            })
            .eq("id", row_id)
            .execute())
    return (resp.data or [None])[0]

def get_history_direct(telefone: str, days: int = 14, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Histórico 1:1 (cliente <-> empresa) dos últimos N dias, do mais antigo para o mais novo.
    Este modelo reflete seu app.py, que grava a mensagem recebida e, depois,
    preenche 'final_out' na mesma linha.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase indisponível para consultar histórico direto")
    rows = (client.table(TABLE)
            .select("*")
            .eq("telefone", telefone)
            .gte("data", _iso(since))
            .order("data", desc=True)
            .limit(limit)
            .execute().data or [])

    items: List[Dict[str, Any]] = []
    # Ordenamos da mais antiga para a mais nova para construir a conversa na ordem certa
    for r in reversed(rows):
        quando = r.get("data")
        msg = r.get("mensagem") or {}
        txt_in = msg.get("text") if isinstance(msg, dict) else (msg or "")
        if txt_in:
            items.append({"when": quando, "who": "cliente", "text": txt_in})

        final_out = r.get("final_out") or ""
        if final_out:
            # usa o mesmo timestamp da linha; se preferir, pode gravar um 'data_out' no app.py e usar aqui
            items.append({"when": quando, "who": "empresa", "text": final_out})

    # limita o total
    return items[-limit:]

def get_history_group(group_id: str, days: int = 14, limit: int = 300) -> List[Dict[str, Any]]:
    """
    Histórico de um grupo (ID do grupo), últimos N dias, do mais antigo para o mais novo.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase indisponível para consultar histórico de grupo")
    rows = (client.table(TABLE)
            .select("*")
            .eq("group_id", group_id)
            .gte("data", _iso(since))
            .order("data", desc=True)
            .limit(limit)
            .execute().data or [])

    items: List[Dict[str, Any]] = []
    for r in reversed(rows):
        quando = r.get("data")
        nome = (r.get("nome") or {}).get("display") or r.get("telefone") or "desconhecido"
        msg = r.get("mensagem") or {}
        txt_in = msg.get("text") if isinstance(msg, dict) else (msg or "")
        if txt_in:
            items.append({"when": quando, "who": nome, "text": txt_in})

        final_out = r.get("final_out") or ""
        if final_out:
            items.append({"when": quando, "who": "empresa", "text": final_out})

    return items[-limit:]

def format_history_for_prompt(history: list, max_chars: int = 2000) -> str:
    """
    Concatena a conversa em linhas do tipo: [quem] texto
    e corta para no máximo max_chars (do fim para o começo).
    """
    lines = [f"[{h['who']}] {h['text']}".strip() for h in history if h.get("text")]
    s = "\n".join(lines)
    if len(s) > max_chars:
        s = s[-max_chars:]
        s = s.split("\n", 1)[-1]  # evita quebrar a primeira linha truncada no meio do tag
    return s
