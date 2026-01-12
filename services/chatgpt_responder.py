# -*- coding: utf-8 -*-
"""ChatGPT responder centralizado para a assistente Julia."""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from supabase_client import get_supabase_client
from services.openai_helpers import cliente

try:
    from helpers import _EMAILS as _KNOWN_EMAILS  # type: ignore
except Exception:  # pragma: no cover - import opcional
    _KNOWN_EMAILS = {}

LOGGER = logging.getLogger("chatgpt.responder")

_BASE_DIR = Path(__file__).resolve().parents[1]
_DATA_DIR = Path(os.getenv("LUCENERA_DATA_DIR") or (_BASE_DIR / "dados"))
_DADOS_PATH = _DATA_DIR / "dados_lucenera.txt"
_POLITICAS_PATH = _DATA_DIR / "politicas_lucenera.txt"

DEFAULT_CHAT_MODEL = (
    os.getenv("CHATGPT_RESPONSE_MODEL")
    or os.getenv("CHATGPT_MODEL")
    or os.getenv("OPENAI_MODEL")
    or "gpt-4o-mini"
)
DEFAULT_TEMPERATURE = float(os.getenv("CHATGPT_RESPONSE_TEMPERATURE", "0.3"))
CONVERSAS_TABLE = os.getenv("CONVERSAS_TABLE", "conversas")
_HISTORY_LIMIT = 10
_MAX_HISTORY_CHARS = 1800

_FILLER_PATTERNS = [
    r"\bse precisar[^\.!\n]*$",
    r"\bqualquer coisa[^\.!\n]*$",
    r"\b(eh|é)\s*s[oó]\s*avisar[^\.!\n]*$",
    r"\b(pode|podem)\s*(me|nos)?\s*chamar[^\.!\n]*$",
    r"\bfico no aguardo[^\.!\n]*$",
    r"\bcomo posso ajudar(\s+voc[eê](s)?)?\??\s*$",
]


@lru_cache(maxsize=2)
def _load_prompt_file(path_str: str) -> str:
    """Carrega prompt de disco com cache simples."""
    path = Path(path_str)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        LOGGER.warning("Prompt base ausente: path=%s", path)
        return ""
    except Exception as exc:  # pragma: no cover - acesso a disco inesperado
        LOGGER.exception("Falha ao ler prompt base: path=%s", path)
        return ""
    return text.strip()


def _prompt_dados() -> str:
    return _load_prompt_file(str(_DADOS_PATH))


def _prompt_politicas() -> str:
    return _load_prompt_file(str(_POLITICAS_PATH))


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_text(row: Dict[str, object]) -> str:
    """Extrai texto da linha da tabela de conversas considerando variações."""
    candidatos: List[Optional[str]] = []
    raw_mensagem = row.get("mensagem")
    if isinstance(raw_mensagem, dict):
        for key in ("text", "texto", "body", "content"):
            candidatos.append(_clean_text(raw_mensagem.get(key)))  # type: ignore[arg-type]
    elif isinstance(raw_mensagem, str):
        candidatos.append(_clean_text(raw_mensagem))

    for key in ("texto", "mensagem", "message", "body", "content"):
        if key in row:
            candidatos.append(_clean_text(row.get(key)))  # type: ignore[arg-type]

    for val in candidatos:
        if val:
            return val
    return ""


def _infer_role(row: Dict[str, object]) -> str:
    """Heurística para identificar se a mensagem veio do cliente ou da empresa."""
    origem = str(row.get("origem") or row.get("role") or "").strip().lower()
    if origem in {"bot", "empresa", "agent", "assistant"}:
        return "empresa"

    from_me = row.get("fromMe") or row.get("from_me") or row.get("sent_by_company")
    if isinstance(from_me, bool) and from_me:
        return "empresa"

    direction = str(row.get("direction") or "").lower()
    if direction in {"out", "outbound"}:
        return "empresa"

    return "cliente"


def _format_history_for_prompt(rows: List[Dict[str, object]]) -> str:
    if not rows:
        return ""
    parts: List[str] = []
    for item in rows:
        text = _extract_text(item)
        if not text:
            continue
        label = "Cliente" if _infer_role(item) == "cliente" else "Equipe"
        parts.append(f"[{label}] {text}")
    if not parts:
        return ""
    history = "\n".join(parts)
    if len(history) > _MAX_HISTORY_CHARS:
        history = history[-_MAX_HISTORY_CHARS:]
        history = history.split("\n", 1)[-1]
    return history


def _fetch_history(user_id: str, limit: int = _HISTORY_LIMIT) -> List[Dict[str, object]]:
    client = get_supabase_client()
    if client is None:
        LOGGER.warning("Supabase indisponível ao buscar histórico do usuário=%s", user_id)
        return []

    order_columns = ["created_at", "data", "createdAt", "timestamp"]
    rows: List[Dict[str, object]] = []
    for col in order_columns:
        try:
            resp = (
                client.table(CONVERSAS_TABLE)
                .select("*")
                .eq("user_id", user_id)
                .order(col, desc=True)
                .limit(limit)
                .execute()
            )
            rows = list(resp.data or [])
            if rows:
                break
        except Exception as exc:
            LOGGER.debug("Falha ao ordenar por %s na tabela %s: %s", col, CONVERSAS_TABLE, exc)
            rows = []
    if not rows:
        return []
    rows.reverse()
    return rows


def _strip_filler_phrases(text: str) -> str:
    out = text
    for pattern in _FILLER_PATTERNS:
        out = re.sub(pattern, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" .;,-")


def _ensure_prefix(text: str, prefix: str = "Julia.") -> str:
    if not text:
        return prefix
    trimmed = text.strip()
    if not trimmed.lower().startswith(prefix.lower()):
        trimmed = f"{prefix} {trimmed.lstrip()}"
    trimmed = trimmed.replace("..", ".")
    return trimmed


def gerar_resposta_com_chatgpt(mensagem_usuario: str, user_id: str) -> str:
    """Gera resposta da Julia usando ChatGPT com prompts e histórico do Supabase."""
    mensagem = _clean_text(mensagem_usuario)
    uid = _clean_text(user_id)
    if not mensagem:
        raise ValueError("mensagem_usuario vazio")
    if not uid:
        raise ValueError("user_id vazio")

    dados = _prompt_dados()
    politicas = _prompt_politicas()
    history_rows = _fetch_history(uid)
    history_block = _format_history_for_prompt(history_rows)

    system_sections = [
        "Você é a Julia, assistente da Lucenera. Responda sempre em português brasileiro.",
        "Mantenha tom profissional, direto, objetivo e humano. Nada de ecoar a pergunta ou usar emojis.",
        "Evite oferecer ajuda genérica ou frases como 'fico no aguardo' ou 'qualquer coisa é só chamar'.",
        "Quando não souber algo, peça apenas uma confirmação objetiva. Não invente respostas.",
        "Sempre inicie a mensagem com 'Julia.' e entregue texto pronto para envio no WhatsApp.",
    ]
    if dados:
        system_sections.append(f"[DADOS_LUCENERA]\n{dados}")
    if politicas:
        system_sections.append(f"[POLITICAS]\n{politicas}")
    if _KNOWN_EMAILS:
        email_lines = [
            "Mapeamento de e-mails confirmados pela equipe:",
            *(f"- {nome.title()}: {email}" for nome, email in sorted(_KNOWN_EMAILS.items())),
        ]
        system_sections.append("\n".join(email_lines))

    system_prompt = "\n\n".join(system_sections)

    user_sections: List[str] = []
    if history_block:
        user_sections.append("Histórico recente:\n" + history_block)
    user_sections.append("Nova mensagem do cliente:\n" + mensagem)
    user_prompt = "\n\n".join(user_sections)

    try:
        completion = cliente.chat.completions.create(  # type: ignore[attr-defined]
            model=DEFAULT_CHAT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:  # pragma: no cover - dependência externa
        LOGGER.exception("Falha ao chamar ChatGPT para user_id=%s", uid)
        raise

    choice = (completion.choices or [None])[0]
    content = ""
    if choice and getattr(choice, "message", None):
        content = getattr(choice.message, "content", "") or ""
    elif choice and isinstance(choice, dict):  # fallback em caso de dicionário bruto
        content = _clean_text(choice.get("message", {}).get("content"))  # type: ignore[call-arg]
    content = _clean_text(content)
    content = _strip_filler_phrases(content)
    return _ensure_prefix(content)


__all__ = ["gerar_resposta_com_chatgpt"]
