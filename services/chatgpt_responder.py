# -*- coding: utf-8 -*-
"""ChatGPT responder centralizado para a assistente Julia."""
from __future__ import annotations

import hashlib
import logging
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam
else:  # pragma: no cover - usado apenas para ajudar tipagem estática
    ChatCompletionMessageParam = Dict[str, Any]

from supabase_client import get_supabase_client
from supabase_helpers import registrar_falha
from services.feedback_respostas import buscar_feedbacks_para_contexto
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
TABLE_MESSAGES = os.getenv("TABLE_MESSAGES") or os.getenv("TABLE") or "mensagens"
try:
    _CTX_HISTORY_LIMIT = int(os.getenv("CTX_HISTORY_LIMIT", "12") or "12")
except ValueError:
    _CTX_HISTORY_LIMIT = 12
_CTX_HISTORY_LIMIT = max(_CTX_HISTORY_LIMIT, 0)
_MAX_HISTORY_CHARS = 1800
DEBUG_PROMPTS = os.getenv("DEBUG_PROMPTS", "false").lower() in {"1", "true", "yes", "on"}
_SHORT_MESSAGE_THRESHOLD = 12
_FEEDBACK_EXAMPLE_LIMIT = 5
_FEEDBACK_SYSTEM_GUIDANCE = "Considere os exemplos reais como referência de tom, clareza e decisão, mas use julgamento próprio."

_SHORT_ACK_PHRASES = {
    "envio sim",
    "envio agora",
    "envio ja",
    "enviei sim",
    "enviei",
    "ok",
    "ok obrigado",
    "ok obrigada",
    "obrigado",
    "obrigada",
    "brigado",
    "brigada",
    "tudo bem",
    "tudo bem?",
    "oi",
    "oi helena",
    "oi helena tudo bem",
    "oi julia",
    "bom dia",
    "boa tarde",
    "boa noite",
    "sim",
    "sim obrigado",
    "sim obrigada",
    "perfeito",
    "maravilha",
    "valeu",
    "tem alguma duvida",
}

_SHORT_ACK_SUBSTRINGS = {
    "tudo bem",
    "envio sim",
    "enviei",
    "bom dia",
    "boa tarde",
    "boa noite",
    "oi helena",
    "oi julia",
    "tem alguma duvida",
    "tem alguma duvida?",
}

_SHORT_RESPONSE_VARIANTS = [
    "Perfeito, obrigado pelo retorno.",
    "Tudo certo por aqui, sigo acompanhando.",
    "Combinado, fico de olho e te aviso.",
    "Tudo bem por aqui, qualquer novidade me chama.",
]


_INTERNAL_AUTHOR_KEYWORDS = {
    "bot",
    "time",
    "time interno",
    "equipe",
    "lucenera",
    "atelier",
    "projetos",
    "admin",
    "estoque",
    "suporte",
    "assistencia",
    "assistente",
    "team",
    "teams",
    "staff",
    "manual",
    "sugestao",
    "julia",
    "helena",
    "vinicius",
    "matheus",
    "coordenacao",
}

_CLIENT_AUTHOR_KEYWORDS = {
    "cliente",
    "client",
    "customer",
    "contato",
    "lead",
    "usuario",
}

_INTERNAL_ORIGEM_HINTS = {
    "bot",
    "human",
    "human_suggestion",
    "internal",
    "team",
    "equipe",
    "staff",
}

_CLIENT_ORIGEM_HINTS = {
    "cliente",
    "client",
}


def _build_short_reply(message: str, seed: str, reason: Optional[str] = None) -> str:
    normalized = _normalize_for_match(message)
    base_variants = _SHORT_RESPONSE_VARIANTS

    if reason == "personal_check":
        from helpers import get_greeting_by_time
        greeting = get_greeting_by_time()
        variants = [
            f"{greeting}, Estou bem tambem, e por ai?",
            f"{greeting}, tudo otimo e com você?",
            f"{greeting}, tudo certo por aqui, e contigo?",
            "Oi! Tudo certo por aqui",
            "Tudo otimo, obrigada por perguntar :)",
        ]
        reply = _select_variant(variants, seed)
        return _normalize_sentence_output(reply)

    if "envio" in normalized or "enviei" in normalized:
        variants = [
            "Perfeito, vou acompanhar o envio e te retorno se faltar algo.",
            "Recebido o envio, sigo monitorando por aqui.",
            "Ótimo, acompanho o envio e te aviso de qualquer pendência.",
        ]
    elif "tem alguma duvida" in normalized or "tem alguma dúvida" in message.lower():
        variants = [
            "Tudo certo por aqui, obrigada por checar.",
            "Tudo bem sim, obrigada por perguntar.",
            "Tudo tranquilo, se surgir dúvida te aviso.",
        ]
    elif any(greeting in normalized for greeting in {"bom dia", "boa tarde", "boa noite"}):
        from helpers import get_greeting_by_time
        greeting = get_greeting_by_time()
        variants = [
            f"{greeting}! Tudo bem por aqui, sigo acompanhando o projeto.",
            f"{greeting}! Estou por aqui e te atualizo se aparecer novidade.",
            f"{greeting}! Está tudo certo por aqui, obrigada pelo contato.",
            f"{greeting}! Sigo acompanhando e te aviso se precisar de algo.",
            f"{greeting}! Tudo tranquilo por aqui, obrigada por avisar.",
            f"{greeting}! Continuo acompanhando e retorno caso surja algo.",
        ]
        reply = _select_variant(variants, seed)
        return _normalize_sentence_output(reply)
    elif any(term in normalized for term in {"oi", "ola"}):
        variants = [
            "Tudo certo por aqui, obrigada por chamar.",
            "Oi! Estou acompanhando e te sinalizo se aparecer novidade.",
        ]
    else:
        variants = base_variants

    reply = _select_variant(variants, seed)
    if not reply:
        reply = base_variants[0]
    return _normalize_sentence_output(reply)

_FILLER_PATTERNS = [
    r"\bse precisar[^\.!\n]*$",
    r"\bqualquer coisa[^\.!\n]*$",
    r"\b(eh|é)\s*s[oó]\s*avisar[^\.!\n]*$",
    r"\b(pode|podem)\s*(me|nos)?\s*chamar[^\.!\n]*$",
    r"\bfico no aguardo[^\.!\n]*$",
    r"\bcomo posso ajudar(\s+voc[eê](s)?)?\??\s*$",
]


JULIA_SYSTEM_PROMPT = """
Você é a Julia, assistente de projetos da Lucenera — Atelier da Luz.
- Nunca diga que é IA, sistema, robô ou automação.
- Fale como uma profissional experiente, consultiva e direta.
- Responda em até duas frases curtas (três apenas se precisar indicar próximo passo).
- Não use frases genéricas como "entendi", "ok", "certo", "recebido", "fico no aguardo", "qualquer coisa é só chamar".
 - Sempre inicie a mensagem final com "**Julia:** " seguido do texto, sem emojis e sem ponto de exclamação.
- Reformule a mensagem do cliente com naturalidade e não a repita literalmente.
- Se faltar informação essencial, faça apenas uma pergunta objetiva.
- Se a mensagem for apenas confirmação/agradecimento, responda com "[SEM RESPOSTA NECESSÁRIA]".
""".strip()

_ORCHESTRATION_GUIDANCE = (
    "Você receberá a mensagem original do cliente, o histórico recente e uma resposta sugerida gerada "
    "pelo backend em Python. Reescreva a resposta final com clareza humana, priorizando o conteúdo real da "
    "mensagem e do histórico para definir tom e foco. Trate a resposta sugerida apenas como ponto de partida "
    "opcional; se ela estiver fora de contexto ou incompleta, construa uma nova resposta coerente. Evite "
    "respostas genéricas como 'ok', 'entendi' ou 'certo'. Se a mensagem for apenas agradecimento, confirmação "
    "ou saudação sem nova demanda, retorne exatamente '[SEM RESPOSTA NECESSÁRIA]'. Quando a mensagem do cliente for "
    "muito curta ou informal, responda de modo acolhedor reconhecendo o contato e não prometa alinhar com a equipe "
    "sem necessidade explícita."
)


def _normalize_for_match(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


def _build_system_prompt(dados: str, politicas: str) -> str:
    sections: List[str] = [JULIA_SYSTEM_PROMPT]
    if dados:
        sections.append(f"[DADOS_LUCENERA]\n{dados}")
    if politicas:
        sections.append(f"[POLITICAS_LUCENERA]\n{politicas}")
    if _KNOWN_EMAILS:
        email_lines = [
            "Mapeamento de e-mails confirmados pela equipe:",
            *(f"- {nome.title()}: {email}" for nome, email in sorted(_KNOWN_EMAILS.items())),
        ]
        sections.append("\n".join(email_lines))
    return "\n\n".join(section for section in sections if section)


def _call_openai_for_response(messages: List[ChatCompletionMessageParam]) -> str:
    if DEBUG_PROMPTS:
        LOGGER.debug("Prompt ChatGPT - payload:%s%s", os.linesep, messages)

    typed_messages = cast(List["ChatCompletionMessageParam"], messages)

    completion = cliente.chat.completions.create(  # type: ignore[attr-defined]
        model=DEFAULT_CHAT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=512,
        messages=typed_messages,
    )

    choice = (completion.choices or [None])[0]
    if choice and getattr(choice, "message", None):
        return _clean_text(getattr(choice.message, "content", "") or "")
    if choice and isinstance(choice, dict):
        return _clean_text(choice.get("message", {}).get("content"))  # type: ignore[call-arg]
    return ""


def _register_history_entry(chat_id: str, content: str, resposta: str) -> None:
    chat_key = (chat_id or "").strip()
    user_text = (content or "").strip()
    assistant_text = (resposta or "").strip()

    if not chat_key or not user_text or not assistant_text:
        return

    client = get_supabase_client()
    if client is None:
        if DEBUG_PROMPTS:
            LOGGER.debug("Supabase indisponível ao registrar histórico para chat_id=%s", chat_key)
        return

    try:
        existing = (
            client.table(TABLE_MESSAGES)
            .select("id,resposta")
            .eq("chat_id", chat_key)
            .eq("content", user_text)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        existing = None
        LOGGER.debug("Consulta de histórico falhou para chat_id=%s: %s", chat_key, exc)

    if existing and getattr(existing, "data", None):
        row_data = existing.data[0]
        if isinstance(row_data, dict):
            resposta_stored = row_data.get("resposta")
            has_resposta = bool(resposta_stored)
            if isinstance(resposta_stored, str):
                has_resposta = bool(resposta_stored.strip())
            if not has_resposta:
                try:
                    client.table(TABLE_MESSAGES).update({"resposta": assistant_text}).eq("id", row_data.get("id")).execute()
                    return
                except Exception as exc:  # pragma: no cover - erro externo
                    LOGGER.debug("Falha ao atualizar resposta histórica chat_id=%s: %s", chat_key, exc)

    try:
        client.table(TABLE_MESSAGES).insert(
            {
                "chat_id": chat_key,
                "thread_id": chat_key,
                "content": user_text,
                "resposta": assistant_text,
            }
        ).execute()
    except Exception as exc:  # pragma: no cover - erro externo
        LOGGER.warning("Não foi possível registrar histórico chat_id=%s: %s", chat_key, exc)


def _build_feedback_examples_block(examples: List[Dict[str, Any]]) -> Tuple[Optional[str], int]:
    lines: List[str] = ["[EXEMPLOS_REAIS]"]
    count = 0
    for idx, example in enumerate(examples, start=1):
        cliente = _clean_text(example.get("mensagem_cliente"))
        resposta = _clean_text(example.get("resposta_humana_correta"))
        if not cliente or not resposta:
            continue
        lines.append(f"Caso {idx}:")
        lines.append(f'Cliente: "{cliente}"')
        lines.append("Equipe respondeu:")
        lines.append(f'"{resposta}"')
        lines.append("")
        count += 1
    if count == 0:
        return None, 0
    if lines[-1] == "":
        lines.pop()
    return "\n".join(lines), count


_ACTION_KEYWORDS: Dict[str, set[str]] = {
    "contato_direto": {
        "posso te ligar", "posso ligar", "posso te chamar", "posso chamar", "tem um tempinho",
        "pode falar", "pode me ligar", "te ligo", "falar com voce", "falar com vc", "preciso falar",
        "tem como falar", "tem como chamar",
    },
    "reclamacao": {
        "reclam", "problema", "defeito", "avaria", "troca", "trocar", "quebrado",
        "nao chegou", "não chegou", "chegou errado", "falha", "atraso", "demora", "garantia",
        "urgente", "prioridade", "erro", "incompleto", "faltando",
    },
    "financeiro": {
        "pix", "pagamento", "comprovante", "boleto", "fatura", "transferencia",
        "transferência", "nota fiscal", "nfe", "nf", "valor", "orcamento", "orçamento",
        "cobranca", "cobrança", "contrato", "pedido", "administrativo", "financeiro",
        "danfe", "reserva", "parcel", "sinal",
    },
    "logistica": {
        "entrega", "entregas", "entregar", "logistica", "logística", "retirada",
        "coleta", "coletar", "remessa", "remessas", "expedicao", "expedição", "romaneio",
        "transportadora", "rastreamento", "rastreio", "chegou", "prazo", "separar material",
        "separacao", "separação", "estoque", "motorista", "cooperador",
    },
    "agendamento": {
        "agenda", "agendar", "agendamento", "agendado", "horario", "horário", "data",
        "calendario", "calendário", "reuniao", "reunião", "visita", "disponibilidade",
        "call", "videochamada", "video chamada", "confirmar horario", "confirmar horário",
    },
    "projeto": {
        "projeto", "luminotecnico", "luminotécnico", "iluminacao", "iluminação", "layout",
        "planta", "memorial", "circuito", "especificacao", "especificação", "pendente",
        "perfil", "spot", "temperatura de cor", "irc", "driver", "fotometria",
    },
    "agradecimento": {
        "obrigado", "obrigada", "agradeco", "agradeço", "perfeito", "deu certo",
        "tudo certo", "maravilha", "valeu",
    },
}

_ACTION_PRIORITY: List[str] = [
    "contato_direto",
    "reclamacao",
    "financeiro",
    "logistica",
    "agendamento",
    "projeto",
    "agradecimento",
]


def _detect_action_label(message: str) -> str:
    texto = _normalize_for_match(message)
    if not texto:
        return "default"
    for label in _ACTION_PRIORITY:
        keywords = _ACTION_KEYWORDS.get(label, set())
        if any(term in texto for term in keywords):
            return label
    return "default"


_ACTION_OPENERS: Dict[str, List[str]] = {
    "default": [
        "recebi sua mensagem",
        "vi seu retorno",
        "obrigada por sinalizar",
        "estou acompanhando por aqui",
    ],
    "contato_direto": [
        "entendi que você quer falar diretamente",
        "vi sua mensagem pedindo ligação",
        "entendi que prefere conversar por voz",
        "vi que deseja contato direto",
    ],
    "financeiro": [
        "vi o comprovante enviado",
        "estou registrando a atualização financeira",
        "acompanho aqui a parte de pagamento",
    ],
    "logistica": [
        "estou acompanhando essa demanda de entrega",
        "ja vou repassar a atualização sobre a entrega",
        "já registrei a necessidade logística",
        "vi o pedido ligado à logística",
    ],
    "agendamento": [
        "ja agendei o pedido de Reunião",
        "acompanho a solicitação de agendamento",
        "já marquei aqui que precisamos ajustar o horário",
        "notei a disponibilidade que você mencionou",
    ],
    "projeto": [
        "anotei os detalhes do projeto",
        "estou acompanhando as informações do projeto",
        "já registrei os pontos técnicos que você trouxe",
        "vi os detalhes de projeto que comentou",
    ],
    "reclamacao": [
        "sinto o transtorno que aconteceu",
        "vi o que houve no seu relato",
        "registrei a situação que você mencionou",
        "estou acompanhando o problema que você descreveu",
    ],
    "agradecimento": [
        "que bom receber essa notícia",
        "fico feliz com o retorno",
        "agradeço o feedback",
        "bom saber que deu certo",
    ],
}

_ACTION_HANDOFFS: Dict[str, List[str]] = {
    "default": [
        "me avisa se quiser ajustar algo.",
        "estou por aqui para o que precisar.",
        "qualquer novidade te sinalizo por aqui.",
        "sigo acompanhando e te mantenho no loop.",
    ],
    "contato_direto": [
        "vou checar se alguém pode te retornar por ligação.",
        "vou ver com a equipe quem pode falar com você agora.",
        "vou alinhar com o time e retorno sobre a ligação.",
        "vou verificar se conseguimos te ligar e te aviso.",
    ],
    "financeiro": [
        "vou validar com o administrativo e te retorno em seguida.",
        "vou confirmar com o financeiro e te atualizo assim que possível.",
        "vou registrar com o administrativo e volto com a confirmação.",
        "vou alinhar com o financeiro e te aviso na sequência.",
    ],
    "logistica": [
        "vou alinhar com o time de logística e te retorno em seguida.",
        "vou verificar com a logística e te posiciono em breve.",
        "vou coordenar com o pessoal de logística e volto com o retorno.",
        "vou checar com a logística e te aviso assim que tiver o status.",
    ],
    "agendamento": [
        "vou conferir os horários com a equipe e te retorno.",
        "vou validar as agendas internas e te posiciono em breve.",
        "vou confirmar a disponibilidade com o time e te aviso na sequência.",
        "vou checar com a equipe e retorno com os horários possíveis.",
    ],
    "projeto": [
        "vou revisar com os arquitetos e te retorno em seguida.",
        "vou confirmar com o time de projeto e te atualizo logo.",
        "vou analisar com os arquitetos e volto com a orientação.",
        "vou alinhar com o time técnico e te trago o posicionamento.",
    ],
    "reclamacao": [
        "vou tratar com a equipe e te retorno com o encaminhamento.",
        "vou acionar o time responsável e volto com a solução.",
        "vou verificar internamente e te atualizo com o próximo passo.",
        "vou analisar com a equipe e te posiciono em seguida.",
    ],
    "agradecimento": [
        "vou repassar ao time e seguimos à disposição.",
        "vou avisar a equipe e permanecemos acompanhando.",
        "vou compartilhar com o pessoal e seguimos por aqui para o que precisar.",
        "vou informar o time e qualquer novidade te aviso.",
    ],
}

_DEFAULT_ACTION_LABEL = "default"

_REQUEST_KEYWORDS = {
    "preciso",
    "poderia",
    "pode me",
    "pode enviar",
    "pode mandar",
    "pode informar",
    "envia",
    "enviar",
    "mandar",
    "informa",
    "informar",
    "confirmar",
    "confirma",
    "gentileza",
    "favor",
    "quando",
    "qual",
    "queria",
}

_IMPORTANT_DETAIL_KEYWORDS = {
    "manha",
    "tarde",
    "noite",
    "hoje",
    "amanha",
    "segunda",
    "terca",
    "quarta",
    "quinta",
    "sexta",
    "sabado",
    "domingo",
    "prazo",
    "horario",
    "agenda",
    "codigo",
    "nf",
    "nota",
    "obra",
    "pedido",
}


_PASSIVE_MESSAGES = {
    "ok",
    "certo",
    "sim",
    "perfeito",
    "beleza",
    "combinado",
    "vi o email",
    "vi o e-mail",
    "vi email",
    "sim vi o email",
    "sim vi email",
    "recebido",
    "entendi",
}

_PASSIVE_TOKEN_WHITELIST = {
    "ok", "okk", "okkk", "certo", "sim", "perfeito", "beleza", "combinado",
    "vi", "email", "e-mail", "o", "a", "ja", "viu", "show", "valeu",
    "obrigado", "obrigada", "brigado", "brigada", "recebido", "entendi",
}

_PASSIVE_SUBSTRINGS = {
    "vi o email",
    "vi o e-mail",
    "vi email",
    "vi e-mail",
    "vi teu email",
    "vi teu e-mail",
    "vi seu email",
    "vi seu e-mail",
}


def _is_passive_ack(message: str) -> bool:
    texto = _normalize_for_match(message)
    if not texto:
        return True
    if texto in _PASSIVE_MESSAGES:
        return True
    clean = re.sub(r"[^a-z0-9\s]", " ", texto)
    clean = re.sub(r"\s+", " ", clean).strip()
    if clean in _PASSIVE_MESSAGES:
        return True
    for frag in _PASSIVE_SUBSTRINGS:
        if frag in clean:
            return True
    tokens = [tok for tok in clean.split() if tok]
    if not tokens:
        return True
    if len(tokens) <= 3 and all(tok in {"sim", "ok", "certo"} for tok in tokens):
        return True
    if all(tok in _PASSIVE_TOKEN_WHITELIST for tok in tokens):
        return True
    return False


def _classify_short_message(message: str) -> Optional[str]:
    normalized = _normalize_for_match(message)
    if not normalized:
        return None
    if _looks_like_personal_check(normalized):
        return "personal_check"
    if any(term in normalized for term in _REQUEST_KEYWORDS):
        return None
    for keywords in _ACTION_KEYWORDS.values():
        if any(term in normalized for term in keywords):
            return None
    if any(char.isdigit() for char in normalized):
        return None
    tokens = [tok for tok in normalized.split() if tok]
    if not tokens:
        return None
    cleaned_tokens = [re.sub(r"[^a-z0-9]+", "", tok) or tok for tok in tokens]
    allowed_tokens = _PASSIVE_TOKEN_WHITELIST | {
        "tudo",
        "bem",
        "bom",
        "dia",
        "boa",
        "noite",
        "tarde",
        "ola",
        "oi",
        "com",
        "voce",
        "vc",
        "ce",
        "e",
        "helena",
        "julia",
        "envio",
        "enviei",
        "sim",
        "perfeito",
        "valeu",
        "obrigado",
        "obrigada",
        "brigado",
        "brigada",
        "de",
        "pra",
        "para",
        "por",
        "ai",
        "aqui",
        "bem",
        "estou",
        "estamos",
        "tem",
        "alguma",
        "duvida",
        "duvidas",
        "tranquilo",
        "tranquila",
    }
    match_type: Optional[str] = None
    if _is_passive_ack(message):
        match_type = "passive_ack"
    elif normalized in _SHORT_ACK_PHRASES:
        match_type = "phrase_match"
    elif any(fragment in normalized for fragment in _SHORT_ACK_SUBSTRINGS):
        match_type = "fragment_match"
    if any(token and token not in allowed_tokens for token in cleaned_tokens):
        return None
    if match_type and len(tokens) <= 7:
        return match_type
    if len(normalized) <= _SHORT_MESSAGE_THRESHOLD and len(tokens) <= 5:
        return "length_tokens"
    return None


_PERSONAL_CHECK_PATTERNS = [
    re.compile(r"\b(tudo|td)\s+bem(?:\s+com\s+(?:voce|vc|ca|ce))?\b", re.IGNORECASE),
    re.compile(r"\bcomo\s+(?:voce|vc|ca|ce)\s+(?:esta|ta|vai)\b", re.IGNORECASE),
    re.compile(r"\btudo\s+certo\b", re.IGNORECASE),
    re.compile(r"\b(e|e ai)\s+(?:voce|vc|ca|ce)\b", re.IGNORECASE),
    re.compile(r"\bta\s+bem\b", re.IGNORECASE),
]


def _looks_like_personal_check(normalized: str) -> bool:
    if not normalized:
        return False
    for pattern in _PERSONAL_CHECK_PATTERNS:
        if pattern.search(normalized):
            return True
    if "tudo bem" in normalized and "?" in normalized:
        return True
    if normalized.startswith(("bom dia", "boa tarde", "boa noite")) and "tudo bem" in normalized:
        return True
    return False


def _select_variant(options: List[str], seed: str) -> str:
    if not options:
        return ""
    if len(options) == 1:
        return options[0]
    digest = hashlib.sha1(seed.encode("utf-8")).digest()
    idx = digest[0] % len(options)
    return options[idx]


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.\?\!])\s+")


def _normalize_sentence_output(sentence: str) -> str:
    if not sentence:
        return ""
    s = sentence.strip()
    if not s:
        return ""
    s = s.replace("!", ".")
    s = re.sub(r"\s+", " ", s)
    s = s.replace(" ,", ",").replace(" .", ".")
    s = s.replace("..", ".")
    if s and s[0].isalpha():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".?":
        s += "."
    return s


def _compose_lead_sentence(action_label: str, seed: str) -> str:
    label = action_label if action_label in _ACTION_OPENERS else _DEFAULT_ACTION_LABEL
    openers = _ACTION_OPENERS.get(label) or _ACTION_OPENERS.get(_DEFAULT_ACTION_LABEL, [])
    handoffs = _ACTION_HANDOFFS.get(label) or _ACTION_HANDOFFS.get(_DEFAULT_ACTION_LABEL, [])
    opener = _select_variant(openers, f"{seed}:opener").strip().rstrip(".")
    handoff = _select_variant(handoffs, f"{seed}:handoff").strip()
    if not opener and not handoff:
        return ""
    opener_sentence = opener[0].upper() + opener[1:] if opener else ""
    handoff_sentence = handoff
    if handoff_sentence and handoff_sentence[0].isupper():
        handoff_sentence = handoff_sentence[0].lower() + handoff_sentence[1:]
    if opener_sentence and handoff_sentence:
        combined = f"{opener_sentence}, {handoff_sentence}"
    else:
        combined = opener_sentence or handoff_sentence
    return _normalize_sentence_output(combined)


def _extract_followup_sentence(raw_text: str) -> Optional[str]:
    if not raw_text:
        return None
    parts = _SENTENCE_SPLIT_RE.split(raw_text.strip())
    candidates: List[tuple[str, str]] = []
    for part in parts:
        normalized = _normalize_sentence_output(part)
        if not normalized:
            continue
        norm_lower = _normalize_for_match(normalized)
        if not norm_lower or norm_lower.startswith("julia"):
            continue
        candidates.append((normalized, norm_lower))
    if not candidates:
        return None
    for sentence, _ in candidates:
        if sentence.endswith("?") or "?" in sentence:
            return sentence
    for sentence, norm_lower in candidates:
        if any(keyword in norm_lower for keyword in _REQUEST_KEYWORDS):
            return sentence
        if any(ch.isdigit() for ch in sentence):
            return sentence
        if any(keyword in norm_lower for keyword in _IMPORTANT_DETAIL_KEYWORDS):
            return sentence
    return None


def _humanize_generated_text(raw_text: str, action_label: str, seed: str) -> str:
    lead = _compose_lead_sentence(action_label, seed)
    followup = _extract_followup_sentence(raw_text)
    sentences: List[str] = []
    if lead:
        sentences.append(lead)
    if followup and followup not in sentences:
        sentences.append(followup)
    if not sentences:
        fallback = _normalize_sentence_output(raw_text)
        return fallback
    combined = " ".join(sentences[:2]).strip()
    return combined


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


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "t", "yes", "y", "sim"}:
            return True
        if lowered in {"0", "false", "f", "no", "n", "nao"}:
            return False
    return None


def _role_from_author_hint(value: Any) -> Optional[str]:
    normalized = _normalize_for_match(str(value)) if value is not None else ""
    if not normalized:
        return None
    if normalized in _CLIENT_AUTHOR_KEYWORDS:
        return "user"
    if normalized in _INTERNAL_AUTHOR_KEYWORDS:
        return "assistant"
    if any(keyword in normalized for keyword in _CLIENT_AUTHOR_KEYWORDS):
        return "user"
    if any(keyword in normalized for keyword in _INTERNAL_AUTHOR_KEYWORDS):
        return "assistant"
    return None


def _role_from_origin_hint(value: Any) -> Optional[str]:
    normalized = _normalize_for_match(str(value)) if value is not None else ""
    if not normalized:
        return None
    if normalized in _CLIENT_ORIGEM_HINTS:
        return "user"
    if normalized in _INTERNAL_ORIGEM_HINTS:
        return "assistant"
    if "cliente" in normalized or "client" in normalized:
        return "user"
    if any(keyword in normalized for keyword in ("bot", "equipe", "time", "teams", "staff")):
        return "assistant"
    return None


def _infer_row_role(
    row: Dict[str, Any],
    *,
    default: str = "user",
    source: Optional[str] = None,
    mensagem_meta: Optional[Dict[str, Any]] = None,
) -> str:
    from_me = _coerce_bool(row.get("fromMe"))
    if from_me is None:
        from_me = _coerce_bool(row.get("from_me"))
    if from_me is True:
        return "assistant"

    direction = row.get("direction") or row.get("flow_direction")
    direction_norm = _normalize_for_match(direction) if direction else ""
    if direction_norm in {"out", "outgoing", "saida", "enviado"}:
        return "assistant"
    if direction_norm in {"in", "incoming", "entrada"} and default == "assistant":
        default = "user"

    metalist: List[Any] = []
    if mensagem_meta and isinstance(mensagem_meta, dict):
        metalist.extend(
            [
                mensagem_meta.get("role"),
                mensagem_meta.get("author"),
                mensagem_meta.get("source"),
                mensagem_meta.get("origem"),
            ]
        )

    hints: List[Any] = [
        row.get("role"),
        row.get("autor"),
        row.get("author"),
        row.get("author_name"),
        row.get("username"),
        row.get("nome"),
        row.get("nome_display"),
        row.get("display_name"),
        row.get("sender"),
        row.get("sender_name"),
        row.get("origem"),
        row.get("source"),
        row.get("grupo"),
        row.get("group"),
        row.get("group_name"),
        row.get("grupo_nome"),
        row.get("autor_nome"),
    ]

    hints.extend(metalist)

    for hint in hints:
        role = _role_from_origin_hint(hint) or _role_from_author_hint(hint)
        if role:
            return role

    if from_me is False:
        return "user"

    return "assistant" if default == "assistant" else "user"


def _extract_row_messages(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(row, dict):
        return []

    entries: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    timestamp = (
        row.get("created_at")
        or row.get("createdAt")
        or row.get("updated_at")
        or row.get("updatedAt")
        or row.get("data")
        or row.get("timestamp")
    )

    def register(role: str, text: Any, source: str) -> None:
        content = _clean_text(text if isinstance(text, str) else str(text) if text is not None else "")
        if not content:
            return
        final_role = "assistant" if role == "assistant" else "user"
        key = (final_role, content)
        if key in seen:
            return
        seen.add(key)
        entries.append(
            {
                "role": final_role,
                "content": content,
                "source": source,
                "timestamp": timestamp,
            }
        )

    content_text = row.get("content")
    if content_text:
        role = _infer_row_role(row, default="user", source="content")
        register(role, content_text, "content")

    resposta_text = row.get("resposta")
    if resposta_text:
        register("assistant", resposta_text, "resposta")

    equipe_text = row.get("resposta_equipe") or row.get("resposta_humana")
    if equipe_text:
        register("assistant", equipe_text, "resposta_equipe")

    final_out = row.get("final_out")
    if final_out:
        register("assistant", final_out, "final_out")

    mensagem = row.get("mensagem")
    if isinstance(mensagem, dict):
        mensagem_text = mensagem.get("text") or mensagem.get("content") or mensagem.get("mensagem") or mensagem.get("body")
        meta = mensagem.get("meta") if isinstance(mensagem.get("meta"), dict) else None
        if mensagem_text:
            default_role = "assistant" if _coerce_bool(row.get("fromMe") or row.get("from_me")) else "user"
            role = _infer_row_role(row, default=default_role, source="mensagem", mensagem_meta=meta)
            register(role, mensagem_text, "mensagem")
    elif isinstance(mensagem, str):
        role = _infer_row_role(row, default="user", source="mensagem")
        register(role, mensagem, "mensagem")

    texto_field = row.get("texto") or row.get("mensagem_texto")
    if texto_field:
        role = _infer_row_role(row, default="user", source="texto")
        register(role, texto_field, "texto")

    return entries


def _slice_history_entries(
    entries: List[Dict[str, Any]],
    history_limit: int,
) -> Tuple[List[Dict[str, Any]], int, int]:
    if history_limit <= 0 or not entries:
        return [], 0, 0

    total_user = sum(1 for item in entries if item.get("role") == "user")
    if total_user <= history_limit:
        assistant_total = sum(1 for item in entries if item.get("role") == "assistant")
        return entries, total_user, assistant_total

    start_index = 0
    user_count = 0
    for idx in range(len(entries) - 1, -1, -1):
        if entries[idx].get("role") == "user":
            user_count += 1
            if user_count > history_limit:
                start_index = idx + 1
                break
        start_index = idx

    trimmed = entries[start_index:]
    user_trimmed = sum(1 for item in trimmed if item.get("role") == "user")
    assistant_trimmed = sum(1 for item in trimmed if item.get("role") == "assistant")
    return trimmed, user_trimmed, assistant_trimmed


def _fetch_history_pairs(chat_id: str, limit: int = _CTX_HISTORY_LIMIT) -> List[Dict[str, Any]]:
    client = get_supabase_client()
    ident = _clean_text(chat_id)
    if client is None or not ident or limit <= 0:
        return []

    order_columns = ["created_at", "updated_at", "data", "createdAt", "timestamp", "id"]
    filters: List[Tuple[str, str]] = [
        ("chat_id", ident),
        ("thread_id", ident),
        ("telefone", ident),
        ("group_id", ident),
    ]
    fetch_limit = max(limit * 2, limit, 1)

    for field, value in filters:
        for col in order_columns:
            try:
                resp = (
                    client.table(TABLE_MESSAGES)
                    .select("*")
                    .eq(field, value)
                    .order(col, desc=True)
                    .limit(fetch_limit)
                    .execute()
                )
            except Exception as exc:
                LOGGER.debug(
                    "Falha ao consultar histórico: tabela=%s filtro=%s=%s order=%s erro=%s",
                    TABLE_MESSAGES,
                    field,
                    value,
                    col,
                    exc,
                )
                continue

            raw_data = resp.data or []
            data: List[Dict[str, Any]] = [item for item in raw_data if isinstance(item, dict)]
            if data:
                data.reverse()
                return data[-fetch_limit:]

    if DEBUG_PROMPTS:
        LOGGER.debug("Histórico não encontrado para chat_id=%s", ident)
    return []


def build_chat_prompt(
    chat_id: str,
    nova_mensagem: str,
    *,
    system_prompt: str,
    final_user_prompt: str,
    history_limit: int = _CTX_HISTORY_LIMIT,
) -> Tuple[List[ChatCompletionMessageParam], int]:
    pairs = _fetch_history_pairs(chat_id, limit=history_limit)
    messages: List[ChatCompletionMessageParam] = []
    history_count = 0

    system_content = system_prompt or JULIA_SYSTEM_PROMPT
    messages.append({"role": "system", "content": system_content})

    normalized_current = _clean_text(nova_mensagem)
    history_entries: List[Dict[str, Any]] = []
    for pair in pairs:
        for entry in _extract_row_messages(pair):
            role = entry.get("role") or "user"
            content = entry.get("content") or ""
            if not content:
                continue
            if normalized_current and role == "user" and content == normalized_current:
                continue
            history_entries.append(entry)

    trimmed_history, user_history_count, assistant_history_count = _slice_history_entries(
        history_entries,
        history_limit,
    )

    for entry in trimmed_history:
        role_value = entry.get("role") or "user"
        content_value = entry.get("content") or ""
        if not content_value:
            continue
        messages.append({"role": role_value, "content": content_value})

    history_count = user_history_count

    messages.append({"role": "user", "content": final_user_prompt})

    if DEBUG_PROMPTS:
        LOGGER.debug(
            "Histórico incluído no prompt: chat_id=%s user_msgs=%d team_msgs=%d total_entries=%d limite=%d",
            chat_id,
            user_history_count,
            assistant_history_count,
            len(trimmed_history),
            history_limit,
        )

    return messages, history_count


def _strip_filler_phrases(text: str) -> str:
    out = text
    for pattern in _FILLER_PATTERNS:
        out = re.sub(pattern, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" .;,-")


def _ensure_prefix(text: str, prefix: str = "**Julia:** ") -> str:
    """Force the response to start with the assistant tag on the same line."""
    trimmed = (text or "").strip()
    if not trimmed:
        return prefix.rstrip()

    # Remove existing expected prefix variants to avoid duplication.
    normalized = trimmed
    known_prefixes = [
        "**julia:**",
        "julia.",
        "julia:",
        "julia -",
    ]
    lower_normalized = normalized.lower()
    for known_prefix in known_prefixes:
        if lower_normalized.startswith(known_prefix):
            normalized = normalized[len(known_prefix):].lstrip(" \n-:")
            break

    body = " ".join(normalized.split())
    if not body:
        return prefix.rstrip()
    return f"{prefix}{body}"


# Esta função gera a resposta da Julia com base na mensagem do cliente e histórico recente.
# O Python apenas monta o contexto (mensagem, intenção, histórico e resposta sugerida) e delega ao GPT
# a redação final. O texto devolvido pelo modelo é usado como está, apenas garantindo o prefixo "**Julia:** ".
def gerar_resposta_com_chatgpt(
    mensagem_usuario: str,
    user_id: str,
    *,
    mensagem_id: Optional[str | int] = None,
    telefone: Optional[str] = None,
) -> str:
    """Gera resposta da Julia usando ChatGPT com prompts e histórico do Supabase."""
    mensagem = _clean_text(mensagem_usuario)
    uid = _clean_text(user_id)
    if not mensagem:
        raise ValueError("mensagem_usuario vazio")
    if not uid:
        raise ValueError("user_id vazio")
    msg_preview = mensagem[:50].replace("\n", " ")
    LOGGER.debug(
        "[DEBUG] Iniciando geração de resposta mensagem=%s user_id=%s preview=%s",
        mensagem_id or uid,
        uid,
        msg_preview,
    )
    try:
        return _gerar_resposta_impl(mensagem, uid, mensagem_id=mensagem_id, telefone=telefone)
    except Exception as exc:
        LOGGER.exception(
            "[❌ ERRO] Falha ao gerar resposta para mensagem=%s user_id=%s",
            mensagem_id or uid,
            uid,
        )
        registrar_falha(
            mensagem_id or uid,
            motivo=str(exc),
            telefone=telefone,
            mensagem=mensagem,
        )
        raise


def _gerar_resposta_impl(
    mensagem: str,
    uid: str,
    *,
    mensagem_id: Optional[str | int],
    telefone: Optional[str],
) -> str:

    # --- INÍCIO PATCH: Priorizar interpretação de mídia ---
    # Se houver interpretação de mídia na meta, usar como base da resposta sugerida
    meta = None
    try:
        # Buscar meta de mensagem do usuário (caso mensagem seja contexto enriquecido)
        from main import supabase
        if telefone:
            # Buscar última mensagem do telefone
            if supabase:
                data = supabase.table("mensagens").select("mensagem").eq("telefone", telefone).order("created_at", desc=True).limit(1).execute().data
                if data and isinstance(data, list):
                    first = data[0] if len(data) > 0 else None
                    if isinstance(first, dict):
                        msg = first.get("mensagem")
                        if isinstance(msg, dict):
                            meta = msg.get("meta") if isinstance(msg.get("meta"), dict) else None
        # fallback: tentar extrair meta de mensagem se mensagem for JSON
        if not meta:
            import json
            try:
                msg_obj = json.loads(mensagem)
                if isinstance(msg_obj, dict):
                    mmeta = msg_obj.get("meta")
                    if isinstance(mmeta, dict):
                        meta = mmeta
            except Exception:
                pass
    except Exception:
        meta = None

    media_interpret = None
    if isinstance(meta, dict):
        ai = meta.get("audio_interpretation")
        ii = meta.get("image_interpretation")
        if isinstance(ai, str) and ai.strip():
            media_interpret = ai.strip()
        elif isinstance(ii, str) and ii.strip():
            media_interpret = ii.strip()

    if isinstance(media_interpret, str) and media_interpret:
        resposta_base = media_interpret
        LOGGER.info(
            "Resposta sugerida baseada em interpretação de mídia para user_id=%s: %s",
            uid,
            resposta_base,
        )
        return _ensure_prefix(resposta_base)
    # --- FIM PATCH: Priorizar interpretação de mídia ---

    short_reason = _classify_short_message(mensagem)
    if short_reason:
        short_reply = _build_short_reply(mensagem, f"{uid}:{mensagem}:short", short_reason)
        LOGGER.info(
            "Resposta curta gerada por heuristica para user_id=%s (motivo=%s)",
            uid,
            short_reason,
        )
        return _ensure_prefix(short_reply)

    action_label = _detect_action_label(mensagem)
    openers = _ACTION_OPENERS.get(action_label, _ACTION_OPENERS.get(_DEFAULT_ACTION_LABEL, []))
    handoffs = _ACTION_HANDOFFS.get(action_label, _ACTION_HANDOFFS.get(_DEFAULT_ACTION_LABEL, []))

    dados = _prompt_dados()
    politicas = _prompt_politicas()
    seed = f"{uid}:{mensagem}"
    resposta_base = _compose_lead_sentence(action_label, seed)
    if not resposta_base:
        fallback_opener = _select_variant(
            _ACTION_OPENERS.get(_DEFAULT_ACTION_LABEL, []), f"{seed}:fallback_opener"
        ).strip()
        fallback_handoff = _select_variant(
            _ACTION_HANDOFFS.get(_DEFAULT_ACTION_LABEL, []), f"{seed}:fallback_handoff"
        ).strip()
        combined = " ".join(part for part in (fallback_opener, fallback_handoff) if part)
        resposta_base = _normalize_sentence_output(combined)
    if not resposta_base:
        resposta_base = "Vou verificar com a equipe da Lucenera e te retorno em seguida."

    heuristicas: List[str] = [
        f"Ação detectada: {action_label or 'default'}.",
        "Priorize o tom e o conteúdo do cliente descritos na mensagem e no histórico.",
        "Use as sugestões abaixo apenas se fizer sentido para a conversa.",
    ]
    if openers:
        heuristicas.append("Aberturas sugeridas (opcional): " + "; ".join(op.capitalize() for op in openers))
    if handoffs:
        heuristicas.append("Encerramentos sugeridos (opcional): " + "; ".join(handoffs))
    heuristicas.append(
        "Lembrete: responda em até duas frases curtas, mantendo tom direto e profissional sem emojis."
    )
    heuristicas.append(
        "Se a mensagem for apenas cumprimento ou confirmação, reconheça com naturalidade sem prometer alinhamento com a equipe."
    )

    feedback_intent = action_label if action_label and action_label != "default" else None
    feedback_examples: List[Dict[str, Any]] = []
    feedback_block: Optional[str] = None
    feedback_count = 0
    try:
        feedback_examples = buscar_feedbacks_para_contexto(
            intencao=feedback_intent,
            categoria=feedback_intent,
            limite=_FEEDBACK_EXAMPLE_LIMIT,
        )
    except Exception:
        LOGGER.exception("Falha ao buscar feedback_respostas para acao=%s", action_label)
        feedback_examples = []

    if feedback_examples:
        feedback_block, feedback_count = _build_feedback_examples_block(feedback_examples)
    if feedback_block:
        heuristicas.append(
            "Use os exemplos reais como referência de tom, clareza e decisão, aplicando julgamento próprio."
        )
        LOGGER.info(
            "Feedback exemplos anexados ao prompt count=%s acao=%s",
            feedback_count,
            feedback_intent or "default",
        )

    heuristicas_text = "\n".join(heuristicas)

    system_sections = [_build_system_prompt(dados, politicas), _ORCHESTRATION_GUIDANCE]
    if feedback_block:
        system_sections.append(_FEEDBACK_SYSTEM_GUIDANCE)
    system_prompt = "\n\n".join(section for section in system_sections if section)

    label_text = action_label or "default"
    resposta_text = resposta_base.strip() or "(Sem resposta sugerida)"

    user_sections = [
        f"[MENSAGEM_CLIENTE]\n{mensagem}",
        f"[INTENCAO_DETECTADA]\n{label_text}",
        f"[RESPOSTA_SUGERIDA]\n{resposta_text}",
    ]
    if feedback_block:
        user_sections.insert(0, feedback_block)
    if heuristicas_text:
        user_sections.append(f"[GUIA_INTERNO]\n{heuristicas_text}")
    final_user_prompt = "\n\n".join(user_sections)

    try:
        messages, history_count = build_chat_prompt(
            chat_id=uid,
            nova_mensagem=mensagem,
            system_prompt=system_prompt,
            final_user_prompt=final_user_prompt,
        )
        if DEBUG_PROMPTS:
            LOGGER.debug(
                "Mensagens preparadas para ChatGPT: total=%d (histórico=%d) mensagem=%s",
                len(messages),
                history_count,
                mensagem_id or uid,
            )
        content = _call_openai_for_response(messages)
    except Exception:  # pragma: no cover - dependência externa
        LOGGER.exception(
            "Falha ao chamar ChatGPT para user_id=%s mensagem=%s",
            uid,
            mensagem_id or uid,
        )
        raise

    if not content:
        return ""
    if "[sem resposta necessaria]" in _normalize_for_match(content):
        LOGGER.info("Modelo sinalizou ausência de resposta para user_id=%s", uid)
        return ""
    content = _clean_text(content)
    _register_history_entry(uid, mensagem, content)
    LOGGER.info(
        "Resposta gerada via GPT para user_id=%s mensagem=%s (acao=%s)",
        uid,
        mensagem_id or uid,
        action_label,
    )
    return _ensure_prefix(content)


__all__ = ["gerar_resposta_com_chatgpt", "build_chat_prompt"]
