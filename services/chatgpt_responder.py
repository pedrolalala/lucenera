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
DEBUG_PROMPTS = os.getenv("DEBUG_PROMPTS", "false").lower() in {"1", "true", "yes", "on"}
_SHORT_MESSAGE_THRESHOLD = 12

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
    "bom dia",
    "boa tarde",
    "boa noite",
    "sim",
    "sim obrigado",
    "sim obrigada",
    "perfeito",
    "maravilha",
    "valeu",
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
}

_SHORT_RESPONSE_VARIANTS = [
    "Perfeito, obrigado pelo retorno.",
    "Tudo certo por aqui, sigo acompanhando.",
    "Combinado, fico de olho e te aviso.",
    "Tudo bem por aqui, qualquer novidade me chama.",
]

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
- Sempre inicie a mensagem final com "Julia." em linha própria, sem emojis e sem ponto de exclamação.
- Reformule a mensagem do cliente com naturalidade e não a repita literalmente.
- Se faltar informação essencial, faça apenas uma pergunta objetiva.
- Se a mensagem for apenas confirmação/agradecimento, responda com "[SEM RESPOSTA NECESSÁRIA]".
""".strip()


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


def _call_openai_for_response(
    mensagem_cliente: str,
    historico_conversa: Optional[str],
    resposta_sugerida: str,
    action_label: str,
    dados: str,
    politicas: str,
    heuristicas: Optional[str] = None,
) -> str:
    historico_block = (historico_conversa or "(Sem histórico recente)").strip()
    resposta_sugerida = resposta_sugerida.strip() or "(Sem resposta sugerida)"
    historico_text = historico_block or "(Sem histórico recente)"
    label_text = action_label or "default"

    user_sections: List[str] = [
        f"[MENSAGEM_CLIENTE]\n{mensagem_cliente}",
        f"[INTENCAO_DETECTADA]\n{label_text}",
        f"[RESPOSTA_SUGERIDA]\n{resposta_sugerida}",
        f"[HISTORICO_CONVERSA]\n{historico_text}",
    ]
    if heuristicas:
        user_sections.append(f"[GUIA_INTERNO]\n{heuristicas}")
    user_prompt = "\n\n".join(user_sections)

    orchestration_guidance = (
        "Você receberá a mensagem original do cliente, o histórico recente e uma resposta sugerida gerada "
        "pelo backend em Python. Reescreva a resposta final com clareza humana, priorizando o conteúdo real da "
        "mensagem e do histórico para definir tom e foco. Trate a resposta sugerida apenas como ponto de partida "
        "opcional; se ela estiver fora de contexto ou incompleta, construa uma nova resposta coerente. Evite "
        "respostas genéricas como 'ok', 'entendi' ou 'certo'. Se a mensagem for apenas agradecimento, confirmação "
        "ou saudação sem nova demanda, retorne exatamente '[SEM RESPOSTA NECESSÁRIA]'. Quando a mensagem do cliente for "
        "muito curta ou informal, responda de modo acolhedor reconhecendo o contato e não prometa alinhar com a equipe "
        "sem necessidade explícita."
    )

    system_prompt = "\n\n".join(filter(None, (_build_system_prompt(dados, politicas), orchestration_guidance)))

    if DEBUG_PROMPTS:
        LOGGER.debug("Prompt ChatGPT - system:%s%sPrompt ChatGPT - user:%s%s",
                     os.linesep, system_prompt, os.linesep, user_prompt)

    completion = cliente.chat.completions.create(  # type: ignore[attr-defined]
        model=DEFAULT_CHAT_MODEL,
        temperature=DEFAULT_TEMPERATURE,
        max_tokens=512,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    choice = (completion.choices or [None])[0]
    if choice and getattr(choice, "message", None):
        return _clean_text(getattr(choice.message, "content", "") or "")
    if choice and isinstance(choice, dict):
        return _clean_text(choice.get("message", {}).get("content"))  # type: ignore[call-arg]
    return ""


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
        "Ok",
        "Certo",
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
        "vou confirmar com a equipe e te retorno em seguida.",
        "vou alinhar com o time e te atualizo em breve.",
        "vou verificar com a equipe e te posiciono assim que puder.",
        "vou repassar internamente e volto com a resposta.",
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
    }
    match_type: Optional[str] = None
    if _is_passive_ack(message):
        match_type = "passive_ack"
    elif normalized in _SHORT_ACK_PHRASES:
        match_type = "phrase_match"
    elif any(fragment in normalized for fragment in _SHORT_ACK_SUBSTRINGS):
        match_type = "fragment_match"
    if match_type and len(tokens) <= 7 and all(tok in allowed_tokens for tok in tokens):
        return match_type
    if len(normalized) <= _SHORT_MESSAGE_THRESHOLD and len(tokens) <= 5 and all(tok in allowed_tokens for tok in tokens):
        return "length_tokens"
    return None


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
    trimmed = (text or "").strip()
    if not trimmed:
        return prefix
    prefix_lower = prefix.lower()
    if trimmed.lower().startswith(prefix_lower):
        body = trimmed[len(prefix):].lstrip(" \n.")
    else:
        body = trimmed
    body = body.replace("..", ".").strip()
    if body:
        return f"{prefix}\n{body}"
    return prefix


# Esta função gera a resposta da Julia com base na mensagem do cliente e histórico recente.
# O Python apenas monta o contexto (mensagem, intenção, histórico e resposta sugerida) e delega ao GPT
# a redação final. O texto devolvido pelo modelo é usado como está, apenas garantindo o prefixo "Julia.".
def gerar_resposta_com_chatgpt(mensagem_usuario: str, user_id: str) -> str:
    """Gera resposta da Julia usando ChatGPT com prompts e histórico do Supabase."""
    mensagem = _clean_text(mensagem_usuario)
    uid = _clean_text(user_id)
    if not mensagem:
        raise ValueError("mensagem_usuario vazio")
    if not uid:
        raise ValueError("user_id vazio")
    short_reason = _classify_short_message(mensagem)
    if short_reason:
        short_reply = _select_variant(_SHORT_RESPONSE_VARIANTS, f"{uid}:{mensagem}:short")
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
    history_rows = _fetch_history(uid)
    history_block = _format_history_for_prompt(history_rows)

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
    heuristicas_text = "\n".join(heuristicas)

    try:
        content = _call_openai_for_response(
            mensagem_cliente=mensagem,
            historico_conversa=history_block,
            resposta_sugerida=resposta_base,
            action_label=action_label,
            dados=dados,
            politicas=politicas,
            heuristicas=heuristicas_text,
        )
    except Exception:  # pragma: no cover - dependência externa
        LOGGER.exception("Falha ao chamar ChatGPT para user_id=%s", uid)
        raise

    if not content:
        return ""
    if "[sem resposta necessaria]" in _normalize_for_match(content):
        LOGGER.info("Modelo sinalizou ausência de resposta para user_id=%s", uid)
        return ""
    content = _clean_text(content)
    LOGGER.info("Resposta gerada via GPT para user_id=%s (acao=%s)", uid, action_label)
    return _ensure_prefix(content)


__all__ = ["gerar_resposta_com_chatgpt"]
