# -*- coding: utf-8 -*-
# type: ignore
from __future__ import annotations
from time import sleep
from helpers import *
import os, json, uuid, time, threading, logging, unicodedata, re, sys
import platform, subprocess  # para matar ngrok e fortalecer autostart
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Sequence

from dotenv import load_dotenv, find_dotenv
from flask import Flask, render_template, render_template_string, request, Response, jsonify, redirect, url_for
import requests  # Teams, ngrok, Z-API

# === OpenAI/serviços
from services.openai_helpers import (
    cliente,
    enrich_row_with_media_text,  # pré-processamento de mídia
)
from services.chatgpt_responder import gerar_resposta_com_chatgpt
from selecionar_persona import selecionar_persona
from selecionar_documento import selecionar_contexto
from services.zapi_client import send_text_from_row, send_text_to
from services.deliveries_flow import handle_event as handle_delivery_event
import re, unicodedata, time
from datetime import datetime, timedelta, timezone
# Diretório base do projeto para localizar recursos auxiliares.
BASE_DIR = Path(__file__).resolve().parent
_DOTENV_PATH = find_dotenv(usecwd=True)
if _DOTENV_PATH:
    load_dotenv(_DOTENV_PATH)
else:
    load_dotenv()
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
log = logging.getLogger("werkzeug")
APP_LOG = logging.getLogger("lucenera")
APP_LOG.setLevel(logging.INFO)
if not APP_LOG.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    _handler.setFormatter(_formatter)
    APP_LOG.addHandler(_handler)
# === Equipes / contatos internos (uso interno; não expor ao cliente)
from services.config_equipes import (
    EQUIPES,
    EQUIPES_AUG,
    INTERNAL_NUMBERS,
    INTERNAL_WHATS,
    decidir_canal_teams_from_row,
    get_teams_webhook_for_channel,
    extrair_intencao_financeiro,
    extrair_intencao_estoque,
    is_internal_message,
    ENTREGADORES_WHATS,
)



GREETINGS_RE = re.compile(
    r"^(oi|ol[aá]|e?ai|boa\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai)[\s\W]*$",
    re.I
)
FOLLOWUP_RE = re.compile(
    r"\b(deu certo|e (ai|a[ií])\?|como ficou|conseguiu|e sobre|e aquela|e o? que|tem novidade|me fala|me retorna|resposta|atualiza)\b",
    re.I
)
LOGISTICA_RE = re.compile(
    r"\b(entrega|prazo|rastrea|instala[cç][aã]o|retirada|nota\s*fiscal|nf|troca|devolu[cç][aã]o|garantia|led|driver|spot|lumin[aá]ria)\b",
    re.I
)
# === Smalltalk (cortesia/ack/reciprocidade) ===
ACK_RE = re.compile(r"\b(obrigad[aoa]|valeu|perfeito|ótimo|otimo|combinado|ok(?:ay)?)\b", re.I)
RECIPROCIDADE_RE = re.compile(r"\b(tudo|td)\s*(bem|bom)\s*(e\s*voc[eê])\b", re.I)

def _row_chat_key(row: dict) -> str:
    phone = str(row.get("telefone") or row.get("from") or "").strip()
    return f"phone:{phone}" if phone else f"anon:{row.get('id') or datetime.now().timestamp()}"


# =====================================================================
# ENV / UTILS
# =====================================================================
def _clean_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None: return None
    return v.strip().strip('"').strip("'")

def _to_bool(val, default=False) -> bool:
    if val is None: return bool(default)
    s = str(val).strip().lower()
    if s in {"1","true","t","yes","y","on","sim"}: return True
    if s in {"0","false","f","no","n","off","nao","não"}: return False
    return bool(default)

def _to_int(val, default=None) -> Optional[int]:
    try: return int(val)
    except Exception: return default

def _now_iso() -> str:
    """Retorna ISO no fuso de São Paulo; fallback para UTC."""
    try:
        if ZoneInfo:
            return datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()

def _normalize_no_accent(s: str) -> str:
    if not isinstance(s, str): return ""
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")

# Flags / conf
APPROVAL_MODE = _to_bool(_clean_env("APPROVAL_MODE"), False)
OUTGOING_ENABLED = _to_bool(_clean_env("OUTGOING_ENABLED"), False)
FORCE_PROCESS_ALL_GROUPS = _to_bool(_clean_env("FORCE_PROCESS_ALL_GROUPS"), False)
IGNORE_GROUPS = _to_bool(_clean_env("IGNORE_GROUPS"), False)
PORT = int(_clean_env("PORT") or "5000")
ALLOW_FROM_ME = _to_bool(_clean_env("ALLOW_FROM_ME"), False)
# Habilita dica de smalltalk para IA (por .env ou default True)
SMALLTALK_HINT = _to_bool(_clean_env("SMALLTALK_HINT"), True)


# Janela de histórico que a IA enxerga (maior ajuda o tom contextual)
CTX_HISTORY_LIMIT = _to_int(_clean_env("CTX_HISTORY_LIMIT"), 20) or 20
if CTX_HISTORY_LIMIT <= 0:
    CTX_HISTORY_LIMIT = 20  # fallback sensato


    # ==== NÚMEROS BLOQUEADOS (não responder / não processar) ====
# Pode sobrescrever por .env com:  BLOCKED_NUMBERS=5511991371513,5511999841405;5511991325496
def _digits_only(s: str) -> str:
    """Remove tudo que não for número (ex.: +, espaços, parênteses)."""
    return "".join(ch for ch in (s or "") if ch.isdigit())

_BLOCKED_FROM_ENV_RAW = os.getenv("BLOCKED_NUMBERS", "")

_BLOCKED_DEFAULT = [
    # Contatos externos bloqueados
    "5511991371513",  # Bia Bueno
    "5511999841405",  # outro informado
    "5511991325496",  # Lá Lampe (X)
    "5511945371200",
    "554192893278",   # Matheus Klems
    "555493635211",

    # === Contatos internos da Lucenera (não responder IA) ===
    "5516996454282",  # Marina
    "5516996464282",  # Thairine
    "5516997000842",  # Thais
    "5516997000042",  # Mariane
    "5516997702520",  # Katia
    "5516981287174",  # Vinicius
]

# Normaliza itens do .env (aceita vírgula ou ponto e vírgula)
_BLOCKED_FROM_ENV = [
    p.strip() for p in _BLOCKED_FROM_ENV_RAW.replace(";", ",").split(",") if p.strip()
]

# === Conjuntos normalizados (só dígitos) ===
BLOCKED_DEFAULT_SET = {_digits_only(x) for x in _BLOCKED_DEFAULT if _digits_only(x)}
BLOCKED_ENV_SET     = {_digits_only(x) for x in _BLOCKED_FROM_ENV if _digits_only(x)}
BLOCKED_INTERNAL    = {_digits_only(x) for x in (INTERNAL_WHATS or []) if _digits_only(x)}  # do config_equipes

# Conjunto final para checagem rápida
BLOCKED_NUMBERS = BLOCKED_DEFAULT_SET | BLOCKED_ENV_SET | BLOCKED_INTERNAL

def is_internal_number(phone: str) -> bool:
    """Retorna True se o número for da equipe interna."""
    return _digits_only(phone) in BLOCKED_INTERNAL

def is_blocked_number(phone: str) -> bool:
    """Retorna True se o número estiver bloqueado (inclui internos)."""
    return _digits_only(phone) in BLOCKED_NUMBERS

print(f">> Números bloqueados ativos: {sorted(BLOCKED_NUMBERS)}", flush=True)
try:
    print(f">> Números internos monitorados: {sorted(INTERNAL_NUMBERS)}", flush=True)
except Exception:
    pass


def _row_is_from_me(row: dict) -> bool:
    """
    Retorna True se essa linha representa mensagem enviada pela empresa (from_me),
    seja vinda do payload Z-API ou registrada internamente.
    Essa função NÃO deve ter efeitos colaterais, apenas leitura.
    """
    if not row:
        return False

    try:
        if row.get("from_me") is True:
            return True
        if row.get("fromMe") is True:
            return True

        msg = row.get("mensagem") or {}
        if isinstance(msg, dict):
            meta = msg.get("meta") or {}
            if meta.get("from_me") is True or meta.get("fromMe") is True:
                return True

        direction = (row.get("direction") or "").lower()
        if direction == "out":
            return True

        origem = str(row.get("origem") or "").strip().lower()
        if origem in {"bot", "human", "bot_api", "outgoing", "sent"}:
            return True
    except Exception:
        return False

    return False


# =====================================================================
# Debounce
# =====================================================================
DEBOUNCE_SECONDS = _to_int(_clean_env("DEBOUNCE_SECONDS"), 60) or 60
DEBOUNCE_MAX_SECONDS = _to_int(_clean_env("DEBOUNCE_MAX_SECONDS"), 85) or 85

_debounce_state: dict[str, dict] = {}
_debounce_lock = threading.Lock()


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _safe_row_id(row: Optional[dict]) -> Optional[int]:
    if not isinstance(row, dict):
        return None
    for key in (ID_COLUMN, "id", "id_num"):
        val = row.get(key)
        if val is None:
            continue
        try:
            if isinstance(val, int):
                return val
            sval = str(val).strip()
            if sval:
                return int(float(sval))
        except Exception:
            continue
    return None


def _format_debounce_timestamp(row: dict) -> str:
    meta = (row.get("mensagem") or {}).get("meta") or {}
    for candidate in (
        row.get("data"),
        meta.get("timestamp_iso_sao_paulo"),
        meta.get("timestamp_iso_utc"),
    ):
        dt = _parse_iso_datetime(candidate)
        if dt:
            try:
                if ZoneInfo:
                    dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
            except Exception:
                pass
            return dt.strftime("%H:%M")
    return ""


_MEDIA_PLACEHOLDERS = {
    "image": "[Imagem recebida]",
    "photo": "[Imagem recebida]",
    "imagem": "[Imagem recebida]",
    "video": "[Vídeo recebido]",
    "audio": "[Áudio recebido]",
    "voice": "[Áudio recebido]",
    "ptt": "[Áudio recebido]",
    "document": "[Documento recebido]",
    "file": "[Arquivo recebido]",
    "pdf": "[Documento recebido]",
    "sticker": "[Sticker recebido]",
}


def _describe_message_for_debounce(row: dict) -> str:
    mensagem = (row.get("mensagem") or {})
    texto = (mensagem.get("text") or "").strip()
    if texto:
        texto = texto.replace("\r\n", "\n").replace("\r", "\n")
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto

    meta = mensagem.get("meta") or {}
    caption = (meta.get("caption") or meta.get("preview") or meta.get("file_name") or "").strip()
    if caption:
        return re.sub(r"\s+", " ", caption)

    msg_type = (meta.get("type") or "").strip().lower()
    if msg_type:
        for key, placeholder in _MEDIA_PLACEHOLDERS.items():
            if key in msg_type:
                return placeholder

    if meta.get("has_media") or meta.get("media_id"):
        return "[Mídia recebida]"

    return "[Conteúdo sem texto]"


def _debounce_sort_key(row: dict) -> tuple[datetime, int]:
    dt = _parse_iso_datetime(row.get("data"))
    if not dt:
        meta = (row.get("mensagem") or {}).get("meta") or {}
        dt = _parse_iso_datetime(meta.get("timestamp_iso_utc") or meta.get("timestamp_iso_sao_paulo"))
    if not dt:
        dt = datetime.fromtimestamp(0, tz=timezone.utc)
    rid = _safe_row_id(row) or 0
    return (dt, rid)


def montar_texto_debounced_para_ia(mensagens: Sequence[dict]) -> str:
    if not mensagens:
        return ""
    linhas: List[str] = []
    for msg in sorted(mensagens, key=_debounce_sort_key):
        conteudo = _describe_message_for_debounce(msg)
        if not conteudo:
            continue
        quem = "Equipe" if msg.get("fromMe") else "Cliente"
        horario = _format_debounce_timestamp(msg)
        if horario:
            linhas.append(f"[{horario}] {quem}: {conteudo}")
        else:
            linhas.append(f"{quem}: {conteudo}")
    return "\n".join(linhas)


def _build_debounce_preview(
    mensagens: Sequence[dict], max_linhas: int = 12
) -> tuple[List[str], str, str]:
    consolidado = montar_texto_debounced_para_ia(mensagens)
    linhas = [ln.strip() for ln in consolidado.splitlines() if ln.strip()]
    if len(linhas) > max_linhas:
        excedente = len(linhas) - max_linhas
        linhas = [f"(+{excedente} anteriores)"] + linhas[-max_linhas:]
    preview = " ".join(linhas)
    if len(preview) > 1800:
        preview = preview[:1797] + "…"
    return linhas, preview, consolidado


def _fetch_debounced_messages(
    row: Optional[dict],
    buffer: Optional[Sequence[dict]] = None,
    window_seconds: Optional[int] = None,
) -> List[dict]:
    if buffer:
        return list(sorted(buffer, key=_debounce_sort_key))
    if not isinstance(row, dict):
        return []

    telefone = (row.get("telefone") or "").strip()
    group_id = row.get("group_id")
    if not supabase or (not telefone and not group_id):
        return [row]

    window = window_seconds or max(int(DEBOUNCE_MAX_SECONDS), int(DEBOUNCE_SECONDS))
    base_ts = (
        _parse_iso_datetime(row.get("data"))
        or _parse_iso_datetime(((row.get("mensagem") or {}).get("meta") or {}).get("timestamp_iso_utc"))
        or datetime.now(timezone.utc)
    )
    cutoff = (base_ts - timedelta(seconds=window + 5)).isoformat()

    try:
        qb = supabase.table(TABLE).select("*").gte("data", cutoff)
        if group_id:
            qb = qb.eq("group_id", group_id)
        else:
            qb = qb.eq("telefone", telefone)

        row_id = _safe_row_id(row)
        if row_id is not None:
            qb = qb.lte(ID_COLUMN, row_id)

        dados = qb.order(ID_COLUMN, desc=False).execute().data or []
    except Exception:
        return [row]

    if not dados:
        return [row]
    return list(sorted(dados, key=_debounce_sort_key))


def _schedule_debounce(chat_key: str, row: dict):
    """Acumula mensagens por chat. Reagenda o disparo até o teto DEBOUNCE_MAX_SECONDS.
       Em vez de notificar no Teams, injeta um resumo do lote no próprio row para aparecer no card de aprovação."""
    now = time.time()
    with _debounce_lock:
        state = _debounce_state.get(chat_key)
        if not state:
            state = {"first_ts": now, "timer": None, "buffer": [row]}
            _debounce_state[chat_key] = state
        else:
            state.setdefault("buffer", []).append(row)

    def _merge_meta(target: dict, extra: dict) -> dict:
        target.setdefault("mensagem", {}).setdefault("meta", {})
        target["mensagem"]["meta"].update(extra or {})
        return target

    def _clear_debounce_meta(target: dict):
        try:
            meta = target.setdefault("mensagem", {}).setdefault("meta", {})
            for k in (
                "debounce_batch_seconds",
                "debounce_batch_lines",
                "debounce_batch_count",
                "debounce_batch_preview",
                "debounce_unified_text",
                "debounce_batch_ids",
                "debounce_batch_before_id",
            ):
                meta.pop(k, None)
        except Exception:
            pass

    def _fire():
        try:
            with _debounce_lock:
                st = _debounce_state.pop(chat_key, None)
            if not st:
                return

            buf = st.get("buffer") or []
            latest = buf[-1] if buf else None
            if not latest:
                return

            debounced_messages = _fetch_debounced_messages(latest, buffer=buf)
            batch_count = len(debounced_messages)
            window_seconds = int(max(1, time.time() - st.get("first_ts", time.time())))

            if batch_count > 1:
                linhas, preview, consolidado = _build_debounce_preview(debounced_messages)
                batch_ids = [rid for rid in (_safe_row_id(m) for m in debounced_messages) if rid is not None]
                meta_extra = {
                    "debounce_batch_seconds": window_seconds,
                    "debounce_batch_lines": linhas,
                    "debounce_batch_count": batch_count,
                    "debounce_batch_preview": preview,
                    "debounce_unified_text": consolidado,
                }
                if batch_ids:
                    meta_extra["debounce_batch_ids"] = batch_ids
                    meta_extra["debounce_batch_before_id"] = min(batch_ids)
                _merge_meta(latest, meta_extra)
                try:
                    latest.setdefault("mensagem", {})["text"] = consolidado
                except Exception:
                    pass
            else:
                _clear_debounce_meta(latest)
                latest["_debounced_messages"] = debounced_messages
                rid = latest.get("id_num") or latest.get("id") or "?"
                print(f">> [debounce] disparando para {chat_key} (id={rid}) com lote={len(buf)}", flush=True)
                processar_inline(latest)

        except Exception as e:
            print(">> debounce fire erro:", e, flush=True)

    elapsed = now - state["first_ts"]
    delay = float(DEBOUNCE_SECONDS)
    if elapsed + delay >= float(DEBOUNCE_MAX_SECONDS):
        delay = max(0.0, float(DEBOUNCE_MAX_SECONDS) - elapsed)

    try:
        txt = ((row.get("mensagem") or {}).get("text") or "").strip()
        if txt and (txt.endswith("?") or txt.endswith(".")):
            delay = min(delay, 4.0)
    except Exception:
        pass

    old = state.get("timer")
    try:
        if old and getattr(old, "is_alive", lambda: False)():
            old.cancel()
    except Exception:
        pass

    t = threading.Timer(delay, _fire)
    t.daemon = True
    state["timer"] = t
    t.start()
    print(f">> [debounce] agendado para {chat_key} em {delay:.1f}s (elapsed={elapsed:.1f}s / max={DEBOUNCE_MAX_SECONDS}s)", flush=True)




# Telefones internos
VINICIUS_PHONE = _clean_env("VINICIUS_PHONE") or _clean_env("ADMIN_PHONE")
MATHEUS_PHONE  = _clean_env("MATHEUS_PHONE")  or _clean_env("LOGISTICS_PHONE")

# Z-API
ZAPI_BASE = _clean_env("ZAPI_BASE") or "https://api.z-api.io"
ZAPI_INSTANCE = _clean_env("ZAPI_INSTANCE") or ""
ZAPI_TOKEN = _clean_env("ZAPI_TOKEN") or ""
ZAPI_CLIENT_TOKEN = _clean_env("ZAPI_CLIENT_TOKEN") or ""
PUBLIC_BASE_URL = _clean_env("PUBLIC_BASE_URL") or _clean_env("APP_PUBLIC_URL")

WEBHOOK_PATH = _clean_env("WEBHOOK_PATH") or "/webhook/whatsapp"
if not WEBHOOK_PATH.startswith("/"): WEBHOOK_PATH = "/" + WEBHOOK_PATH

ZAPI_AUTOCONFIG_WEBHOOKS = _to_bool(_clean_env("ZAPI_AUTOCONFIG_WEBHOOKS"), True)
ZAPI_AUTOCONFIG_INTERVAL = _to_int(_clean_env("ZAPI_AUTOCONFIG_INTERVAL"), 30) or 30
ZAPI_WEBHOOK_MODE = (_clean_env("ZAPI_WEBHOOK_MODE") or "all").strip().lower()  # all | receive_only

# TEAMS
TEAMS_WEBHOOK_URL = _clean_env("TEAMS_WEBHOOK_URL") or ""
TEAMS_WEBHOOK_ADMIN = _clean_env("TEAMS_WEBHOOK_ADMIN") or ""
TEAMS_WEBHOOK_ENTREGAS = (
    _clean_env("TEAMS_WEBHOOK_ENTREGAS")
    or _clean_env("TEAMS_WEBHOOK_ENTREGAFINALIZADA")
    or ""
)
TEAMS_ACTION_TOKEN = _clean_env("TEAMS_ACTION_TOKEN") or ""

# ngrok
NGROK_BIN = _clean_env("NGROK_BIN") or "ngrok"
NGROK_REGION = _clean_env("NGROK_REGION") or "sa"
NGROK_AUTHTOKEN = _clean_env("NGROK_AUTHTOKEN") or ""
NGROK_AUTOSTART = _to_bool(_clean_env("NGROK_AUTOSTART"), False)
NGROK_KILL_ON_START = _to_bool(_clean_env("KILL_NGROK_ON_BOOT") or _clean_env("NGROK_KILL_ON_START"), True)

# Tabela
TABLE = _clean_env("TABLE") or "mensagens"
ID_COLUMN = _clean_env("ID_COLUMN") or "id_num"
DELIVERY_CALLBACKS_TABLE = _clean_env("DELIVERY_CALLBACKS_TABLE") or "whatsapp_delivery_callbacks"

# Finalizadores e limpeza
_FINALIZER_TERMS = {
    "ok","okk","okkk","okay","td bem","tudo bem","blz","beleza","ta bom","tá bom",
    "ta certo","tá certo","certo","show","valeu","vlw","obrigado","obrigada","obg",
    "tmj","perfeito","fechou","combinado","confirmado","joia","jóia","maravilha","para vocês também"
    }
_EMOJI_FINALIZERS = {"👍","👍🏻","👍🏼","👍🏽","👍🏾","👍🏿","👌","🤝","🙏","🙂","😊","😉","✅","✔️","✌️","👊","👏","🙌","❤️","❤"}

def _only_emojis(s: str) -> bool:
    if not s: return False
    stripped = re.sub(r"[ \t\n\r,.!?;:()\[\]{}\"'`~\-_/\\|]+", "", s)
    if not stripped:
        return False
    has_word = any(ch.isalnum() for ch in stripped)
    return not has_word

def is_finalizing_message(texto: str) -> bool:
    if not isinstance(texto, str): return False
    t_raw = (texto or "").strip()
    if not t_raw: return False
    tn = _normalize_no_accent(
        t_raw.replace(".", "").replace("!", "").replace(",", "").replace(";", "")
    ).strip()
    if len(tn) <= 20:
        if tn in _FINALIZER_TERMS:
            return True
        ws = tn.split()
        if 1 <= len(ws) <= 3 and any(w in _FINALIZER_TERMS for w in ws):
            return True
    if _only_emojis(t_raw) and any(e in t_raw for e in _EMOJI_FINALIZERS):
        return True
    return False

_FILLER_PATTERNS = [
    r"\bse precisar[^\.!\n]*$",
    r"\bqualquer coisa[^\.!\n]*$",
    r"\b(eh|é)\s*s[oó]\s*avisar[^\.!\n]*$",
    r"\b(pode|podem)\s*(me|nos)?\s*chamar[^\.!\n]*$",
    r"\bfico no aguardo[^\.!\n]*$",
    r"\bcomo posso ajudar(\s+voc[eê](s)?)?\??\s*$",
    # Remover frases robotizadas comuns que o modelo pode gerar
    r"\b(recebi sua mensagem|mensagem recebida|recebido|entendi)\b[^\.!\n]*$",
]
def _strip_filler_phrases(s: str) -> str:
    out = s or ""
    for rx in _FILLER_PATTERNS:
        out = re.sub(rx, "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip(" .;,-")


def _humanize_robotic_response(resposta: str, sender_name: Optional[str], original_msg: str) -> str:
    """Detecta padrões robóticos e reescreve para um tom humano mantendo 'Julia.' prefixo.

    - Se a resposta contém frases como 'recebi sua mensagem' ou 'entendi', reescreve.
    - Para saudações curtas, gera uma saudação calorosa via _gentle_greeting_reply.
    - Para pedidos que exigem verificação, retorna um dos templates aprovados.
    """
    if not resposta:
        return resposta
    r = (resposta or "").strip()
    low = r.lower()
    # padrões que consideramos "robóticos"
    robot_patterns = ["recebi sua mensagem", "mensagem recebida", "entendi", "recebido", "estou verificando", "vou verificar"]
    if not any(p in low for p in robot_patterns):
        return resposta

    # Se a mensagem original for uma saudação, devolver saudação humanizada
    try:
        if is_greeting(original_msg):
            name = (sender_name or "").strip()
            gen = _gentle_greeting_reply(original_msg, name if name else None)
            if gen:
                return gen if gen.lower().startswith("julia.") else f"Julia. {gen}"
    except Exception:
        pass

    low_orig = (original_msg or "").lower()
    if "vídeo" in low_orig or "video" in low_orig or "anexo" in low_orig:
        return "Julia. Já te retorno com as observações em breve"

    needs_check = ["desconto", "fornecedor", "prazo", "disponibilidade", "confirmar", "verificar", "preço", "preco", "orçamento", "orcamento"]
    for k in needs_check:
        if k in low_orig:
            return "Julia. Vou verificar com a equipe e retorno com a atualização sobre os itens"

    # Fallback: saudação curta e humana
    first = (sender_name or "").split()[0] if sender_name else ""
    if first:
        return f"Julia. Oi {first}! Tudo ótimo, e você?"
    return "Julia. Oi! Tudo ótimo, e você?"

# =====================================================================
# SUPABASE CLIENT
# =====================================================================
try:
    from supabase_client import get_supabase_client, column_exists as _supabase_column_exists
    supabase = get_supabase_client()
    if supabase:
        print(">> Supabase client: OK", flush=True)
    else:
        print(">> Supabase client: indisponível (verifique SUPABASE env)", flush=True)
except Exception as e:
    supabase = None
    _supabase_column_exists = None
    print(">> Supabase client: FALHOU no import ->", e, flush=True)

# =====================================================================
# PROMPTS
# =====================================================================
PROMPTS_DIR = Path(os.getenv("LUCENERA_DATA_DIR") or (BASE_DIR / "dados"))
DADOS_FILE = PROMPTS_DIR / "dados_lucenera.txt"
POLITICAS_FILE = PROMPTS_DIR / "politicas_lucenera.txt"
PROMPT_DADOS = ""; PROMPT_POLITICAS = ""

def _read_textsafe(p: Path) -> str:
    try:
        if p.exists(): return p.read_text(encoding="utf-8", errors="ignore").strip()
        else: print(f">> Aviso: arquivo não encontrado: {p}", flush=True)
    except Exception as e:
        print(f">> Falha lendo {p}: {e}", flush=True)
    return ""

def _load_prompts() -> None:
    global PROMPT_DADOS, PROMPT_POLITICAS
    PROMPT_DADOS = _read_textsafe(DADOS_FILE)
    PROMPT_POLITICAS = _read_textsafe(POLITICAS_FILE)
    print(f">> Prompts carregados de: {PROMPTS_DIR}")
    print(f"   - dados_lucenera.txt: {len(PROMPT_DADOS)} chars")
    print(f"   - politicas_lucenera.txt: {len(PROMPT_POLITICAS)} chars")
_load_prompts()

SYSTEM_RULES = (
    "Você é a assistente virtual da Lucenera (WhatsApp da Thais), respondendo em pt-BR. "
    "Fale de forma humana e natural; nunca diga que é IA.\n\n"
    "- Se houver [HISTORICO], use-o para manter o fio da conversa. Evite saudações genéricas se a última fala no histórico foi da empresa."
    "Identidade e tom:\n"
    "- Responda como se fosse a Julia. (O prefixo 'Julia.' será adicionado pelo formatador.)\n"
    "- 1–2 frases (máx. 3 se precisar conectar ideia + próxima ação objetiva).\n"
    "- Sem emojis e sem ponto de exclamação.\n"
    "- Não ecoe literalmente o que a pessoa escreveu e não use o nome do contato por padrão.\n"
    "- Evite frases genéricas de fechamento: 'qualquer coisa é só avisar', 'fico à disposição', 'no aguardo'.\n"
    "- Nunca use 'Como posso ajudar?' ou variações.\n\n"
    "Robustez e contexto:\n"
    "- Se faltar UM dado essencial (modelo, medida, prazo etc.), faça UMA pergunta objetiva, sem rodeios.\n"
    "- Mensagens apenas de cortesia/saudação (ex.: 'bom dia', 'tudo bem?') devem ser silenciadas.\n"
    "- Mensagens de confirmação simples (ex.: 'ok', 'combinado', emojis de ok) encerram sem resposta.\n"
    "- Para mídia/arquivos: confirme recebimento e diga que vai analisar antes de retornar.\n"
    "- Se houver urgência, foque na próxima ação prática (endereços, prazos, responsável).\n\n"
    "Produtos/financeiro:\n"
    "- Consulte planilhas/ferramentas quando disponível; não revele custo, fornecedor ou margem.\n\n"
    "Dados institucionais:\n"
    "- Endereço: Rua Ayrton Roxo nº 867, Alto da Boa Vista — Ribeirão Preto. estoque: R. Dr. Hugo Fortes, 1010 - Parque Industrial Lagoinha, Ribeirão Preto - SP, 14095-260\n"
)

# Regras adicionais para evitar respostas robóticas e guiar smalltalk
SYSTEM_RULES = SYSTEM_RULES + (
    "\n\nRegras de estilo (IMPORTANTE):\n"
    "- NUNCA responda apenas com frases como 'Recebi sua mensagem', 'Mensagem recebida', 'Entendi' ou 'Recebido'.\n"
    "- Para saudações, responda com uma saudação calorosa seguida de uma pergunta curta quando apropriado (ex.: 'Oi! Tudo ótimo, e você? Posso ajudar em algo?').\n"
    "- Se o histórico mostra que o cliente iniciou a conversa, priorize uma resposta que reconecte (saudação + pergunta).\n"
    "- Evite frases padronizadas de fechamento ('qualquer coisa é só avisar', 'fico à disposição').\n"
    "- Exemplos (RUIM -> BOM):\n"
    "  RUIM: 'Recebi sua mensagem. Se precisar, estou por aqui.'\n"
    "  BOM:  'Oi! Tudo ótimo, e você? Posso ajudar com algo agora?'\n"
)

# =====================================================================
# Seletores robustos
# =====================================================================
def _safe_selecionar_persona(is_group: bool, group_name: str, sender_name: str):
    try:
        gname = (group_name or "").strip(); sname = (sender_name or "").strip()
        # selecionar_persona espera (mensagem_usuario: str, acao_prevista: Optional[str]=None)
        mensagem_usuario = sname if sname else (gname if gname else "")
        try:
            return selecionar_persona(mensagem_usuario)
        except TypeError:
            try:
                return selecionar_persona(str(mensagem_usuario))
            except Exception:
                return None
    except Exception:
        return None

def _safe_selecionar_contexto(row: dict):
    try:
        texto = ((row.get("mensagem") or {}).get("text") or "").strip()
        gname = (row.get("group_name") or row.get("Group_name") or "").strip()
        sname = (row.get("sender_name") or (row.get("nome") or {}).get("display") or "").strip()
        tel   = (row.get("telefone") or "") or ""
        gid   = (row.get("group_id") or "") or ""
        # selecionar_contexto espera normalmente uma string (mensagem do usuário).
        # Para compatibilidade com versões antigas, primeiro tentamos passar a string
        # e cair em fallbacks simples. Evitamos passar dicts diretamente porque algumas
        # versões do cliente OpenAI reclamavam de 'messages[].content' contendo objetos.
        try:
            return selecionar_contexto(texto)
        except Exception:
            try:
                return selecionar_contexto(str(texto))
            except Exception:
                return "dados"
    except Exception:
        return None

# =====================================================================
# Roteamento + notificação
# =====================================================================
_ADMIN_TERMS = {"pagamento","comprovante","pix","boleto","fatura","vencimento","nota fiscal","nfe","nf-e","2a via","2ª via","segunda via","cobrança","cobranca","duplicata","baixa","protesto"}
_LOG_TERMS = {"entrega","retirada","separacao","separação","romaneio","rastreio","rastreamento","transportadora","motoboy","motorista","coleta","instalação","instalacao","instalar","chegou","não chegou","nao chegou","faltando","divergencia","divergência","avaria","quebrado","risco","defeito","estoque","prazo","l35","perfil","luminária","luminaria","material","pedido","nota de remessa","remessa"}

def _should_suppress_logistica(txt: str) -> bool:
    """Bloqueia acionamento de logística em mensagens genéricas (como incluir item no orçamento)."""
    t = (txt or "").lower()
    # Exemplo: "material do espelho vamos incluir no orçamento"
    if "espelho" in t and ("incluir" in t or "inclus") and (
        "orcamento" in t or "orçamento" in t or "no orçamento" in t
    ):
        return True
    return False

def _classify_route(txt: str) -> Optional[str]:
    if _should_suppress_logistica(txt):
        return None
    message = txt or ""
    if extrair_intencao_financeiro(message):
        return "admin"
    if extrair_intencao_estoque(message):
        return "log"

    t = _normalize_no_accent(message)
    if any(term in t for term in _ADMIN_TERMS):
        return "admin"
    if any(term in t for term in _LOG_TERMS):
        return "log"
    return None


def _notify_internal(route: str, txt: str, telefone_cli: Optional[str], group_name: Optional[str]) -> None:
    try:
        if not OUTGOING_ENABLED:
            print("[DRY RUN] Notificação interna bloqueada (OUTGOING_ENABLED=0)."); return
        destino = None; titulo = None
        if route == "admin":
            destino = VINICIUS_PHONE; titulo = "Acionar Vinícius - Administrativo"
            corpo = f"Vinícius, por favor verificar um assunto administrativo/financeiro.\nResumo: {txt[:400]}\nOrigem: {'grupo ' + (group_name or '') if group_name else ('contato ' + (telefone_cli or ''))}"
        elif route == "log":
            destino = MATHEUS_PHONE; titulo = "Acionar Matheus - Estoque/Logística"
            corpo = f"Matheus, por favor verificar entrega/estoque.\nResumo: {txt[:400]}\nOrigem: {'grupo ' + (group_name or '') if group_name else ('contato ' + (telefone_cli or ''))}"
        else:
            return
        if not destino:
            print(f">> Aviso interno ({route}) NÃO enviado: número destino não configurado no .env.", flush=True); return
        ok = send_text_to(phone=destino, message=f"{titulo}\n\n{corpo}")
        print(f">> Notificação interna [{route}] enviada={ok} para {destino}", flush=True)
    except Exception as e:
        print(">> Falha ao notificar interno:", e, flush=True)

# =====================================================================
# Prompt Guard
# =====================================================================
def _is_gibberish(txt: str) -> bool:
    if not isinstance(txt, str): return True
    s = txt.strip()
    if not s: return True
    letters = sum(ch.isalpha() for ch in s)
    digits = sum(ch.isdigit() for ch in s)
    spaces = sum(ch.isspace() for ch in s)
    if len(s) >= 8 and (letters + digits) / max(1, len(s) - spaces) < 0.35: return True
    if re.search(r"(.)\1{4,}", s): return True
    return False

def _is_greeting_only(txt: str) -> bool:
    if not isinstance(txt, str):
        return False
    t = _normalize_no_accent(txt or "")
    t = re.sub(r"^[\s,;:.!¡¿?…-]+|[\s,;:.!¡¿?…-]+$", "", t)
    rx = r"^(oi|ola|olá|hello|hi|bom dia|boa tarde|boa noite)(\s*,?\s*(tudo bem|td bem|tudo bom|como vai))?\s*\??$"
    return re.match(rx, t, flags=re.IGNORECASE) is not None

def _needs_clarify(txt: str) -> Optional[str]:
    if not isinstance(txt, str) or not txt.strip():
        return "__ignore_greeting__"
    if _is_greeting_only(txt):
        return "__ignore_greeting__"
    if _is_gibberish(txt):
        return "Não consegui entender bem. Pode explicar em uma frase o que você precisa?"

    t = _normalize_no_accent(txt)
    _VAGUE = {"preco","preço","quanto custa","valores","orçamento","orcamento","tem?"}
    _DOMAIN = {"luminotecnico","luminotécnico","projeto","perfil","led","spot","cct","irc","luminaria","luminária","iluminacao","iluminação","pendente","trilho","driver","fotometria","memorial","layout"}
    _DOMAIN_NORM = {_normalize_no_accent(x) for x in _DOMAIN}
    if any(k in t for k in _VAGUE) and not any(k in t for k in _DOMAIN_NORM):
        return "De qual produto/medida você precisa o preço? (ex: perfil L35, 1 metro)"
    return None

# =====================================================================
# Contexto (HISTÓRICO)
# =====================================================================
def _fmt_hhmm(ts: Optional[str]) -> str:
    try:
        if not ts:
            return ""
        dt = datetime.fromisoformat(ts)
        if ZoneInfo:
            dt = dt.astimezone(ZoneInfo("America/Sao_Paulo"))
        return dt.strftime("%d/%m %H:%M")
    except Exception:
        return ""

def _fetch_recent_texts_for_chat(
    telefone: Optional[str],
    group_id: Optional[str],
    limit: int = 12,
    before_id: Optional[int] = None,
    window_hours: int = 24,
    skip_ids: Optional[Sequence[int]] = None,
) -> List[str]:
    if not supabase:
        return []
    try:
        from datetime import datetime, timezone, timedelta
        cutoff_iso = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
        qb = (supabase.table(TABLE)
            .select(f"{ID_COLUMN},mensagem,telefone,group_id,fromMe,data")
            .gte("data", cutoff_iso)
            .order(ID_COLUMN, desc=True))
        if group_id:
            qb = qb.eq("group_id", group_id)
        elif telefone:
            qb = qb.eq("telefone", (telefone or "").strip())
        if before_id:
            qb = qb.lt(ID_COLUMN, before_id)
        # IMPORTANTE: incluir tanto mensagens do cliente quanto mensagens enviadas
        # pela empresa no histórico usado para contexto (fromMe True/False).
        # Portanto NÃO aplicamos filtro para remover mensagens with fromMe=True.
        rows = (qb.limit(max(limit, 1)).execute().data) or []
        skip_set: set[int] = set()
        for sid in skip_ids or []:
            try:
                skip_set.add(int(sid))
            except Exception:
                continue
        lines: List[str] = []
        for r in rows:
            rid = _safe_row_id(r)
            if rid is not None and rid in skip_set:
                continue
            msg = (r.get("mensagem") or {}) or {}
            txt = (msg.get("text") or "").strip()
            if not txt:
                continue
            who = "Eu" if r.get("fromMe") else "Cliente"
            stamp = ""
            try:
                from dateutil import parser, tz  # se não tiver, pode simplificar
                dt = parser.isoparse(r.get("data"))
                stamp = dt.astimezone(tz.tzlocal()).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
            lines.append(f"[{stamp}] {who}: {txt}")
        return list(reversed(lines))
    except Exception as e:
        print(">> _fetch_recent_texts_for_chat erro:", e, flush=True)
        return []


def _collect_history_for_routing(row: Optional[dict], limit: int = 8) -> List[str]:
    if not isinstance(row, dict):
        return []

    telefone = (row.get("telefone") or "").strip() or None
    group_id = row.get("group_id") or None

    meta = (row.get("mensagem") or {}).get("meta") or {}
    skip_ids = meta.get("debounce_batch_ids") or []

    before_id_val = row.get(ID_COLUMN)
    try:
        before_id = int(before_id_val) if before_id_val is not None else None
    except (TypeError, ValueError):
        before_id = None

    debounce_before = meta.get("debounce_batch_before_id")
    if debounce_before is not None:
        try:
            before_id = int(debounce_before)
        except (TypeError, ValueError):
            pass

    return _fetch_recent_texts_for_chat(
        telefone=None if group_id else telefone,
        group_id=group_id,
        limit=limit,
        before_id=before_id,
        skip_ids=skip_ids,
    )


def _analysis_to_text(analysis: Any) -> str:
    if analysis is None:
        return ""
    if isinstance(analysis, str):
        return analysis
    if isinstance(analysis, dict):
        return " ".join(_analysis_to_text(v) for v in analysis.values())
    if isinstance(analysis, (list, tuple, set)):
        return " ".join(_analysis_to_text(v) for v in analysis)
    return str(analysis)


_NUM_WORDS_MAP = {
    "um": "1",
    "dois": "2",
    "tres": "3",
    "quatro": "4",
    "cinco": "5",
    "seis": "6",
    "sete": "7",
    "oito": "8",
    "nove": "9",
    "dez": "10",
    "onze": "11",
    "doze": "12",
    "treze": "13",
    "quatorze": "14",
    "quinze": "15",
    "dezesseis": "16",
    "dezessete": "17",
    "dezoito": "18",
    "dezenove": "19",
    "vinte": "20",
}


def _extract_numeric_tokens(normalized_text: str) -> List[str]:
    numbers = list(re.findall(r"\b\d+[\.,]?\d*\b", normalized_text))
    for word, num in _NUM_WORDS_MAP.items():
        if re.search(rf"\b{word}\b", normalized_text):
            numbers.append(num)
    seen: set[str] = set()
    ordered: List[str] = []
    for n in numbers:
        key = n.strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def _sanity_check_history_dm(telefone: str, row_id: int) -> bool:
    lines = _fetch_recent_texts_for_chat(
        telefone=(telefone or "").strip(),
        group_id=None,
        limit=CTX_HISTORY_LIMIT,
        before_id=row_id,
    )
    assert len(lines) <= CTX_HISTORY_LIMIT, f"veio {len(lines)} > {CTX_HISTORY_LIMIT}"
    return True


def _fetch_human_suggestions(telefone: Optional[str], limit: int = 3) -> List[Dict[str, Any]]:
    if not supabase or not telefone:
        return []
    try:
        rows = (
            supabase.table(TABLE)
            .select(f"{ID_COLUMN},mensagem,data,origem")
            .eq("telefone", (telefone or "").strip())
            .eq("origem", "human_suggestion")
            .order(ID_COLUMN, desc=True)
            .limit(max(1, limit))
            .execute()
            .data
            or []
        )
        suggestions: List[Dict[str, Any]] = []
        for r in rows:
            msg = (r.get("mensagem") or {}) if isinstance(r.get("mensagem"), dict) else {}
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            meta = msg.get("meta") or {}
            suggestions.append(
                {
                    "text": text,
                    "client_excerpt": (meta.get("client_excerpt") or "").strip(),
                    "created_at": r.get("data"),
                }
            )
        return suggestions
    except Exception as e:
        print(">> _fetch_human_suggestions erro:", e, flush=True)
        return []
# =====================================================================
# INSERÇÃO VIA WEBHOOK Z-API
# =====================================================================
def _ts_ms_to_iso(ms: int | None) -> Optional[str]:
    try:
        if ms is None:
            return None
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


def _extract_text_from_payload(p: dict) -> str:
    if not isinstance(p, dict):
        return ""
    t = p.get("text")
    if isinstance(t, dict):
        m = t.get("message")
        if isinstance(m, str) and m.strip():
            return m.strip()
        if isinstance(m, (bytes, bytearray)):
            try:
                return m.decode("utf-8", "ignore").strip()
            except Exception:
                return m.decode("latin1", "ignore").strip()
    for k in ("message", "text", "body", "msg", "content"):
        v = p.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    img = p.get("image")
    if isinstance(img, dict):
        caption = (img.get("caption") or "").strip()
        if caption:
            return caption
        url = img.get("imageUrl") or img.get("thumbnailUrl")
        if url:
            return f"[Imagem recebida: {url}]"
    vid = p.get("video")
    if isinstance(vid, dict):
        caption = (vid.get("caption") or "").strip()
        if caption:
            return caption
        url = vid.get("videoUrl")
        if url:
            return f"[Vídeo recebido: {url}]"
    aud = p.get("audio")
    if isinstance(aud, dict) and aud.get("audioUrl"):
        return f"[Áudio recebido: {aud['audioUrl']}]"
    doc = p.get("document")
    if isinstance(doc, dict) and doc.get("documentUrl"):
        return f"[Documento recebido: {doc['documentUrl']}]"
    return ""


def _save_in_supabase_from_zapi(
    payload: dict,
    *,
    parsed: Optional[dict] = None,
    internal_only: bool = False,
) -> Optional[dict]:
    if not supabase:
        print(">> [ERRO] Supabase indisponível.")
        return None

    raw_payload = payload or {}
    try:
        norm = parsed if isinstance(parsed, dict) else parse_zapi_payload(raw_payload)
    except Exception as e_parse:
        print(">> aviso: falha ao normalizar payload Z-API:", e_parse, flush=True)
        norm = {}

    txt = (norm.get("text") or "").strip()
    if not txt:
        txt = (_extract_text_from_payload(raw_payload) or "").strip()
        if txt:
            print(">> [INFO] Fallback de texto aplicado (payload.text/message).", flush=True)

    telefone = (norm.get("telefone") or norm.get("chat_phone") or "").strip()
    is_group = bool(norm.get("is_group"))
    group_id = norm.get("group_id")
    group_name = norm.get("group_name")
    sender_name = norm.get("sender_name")
    from_me = bool(norm.get("fromMe"))
    from_api = bool(norm.get("fromApi"))
    event_type = (norm.get("type") or "").strip()
    msg_status = (norm.get("status") or "").strip().lower()
    ts_iso_utc = norm.get("timestamp_iso_utc")
    ts_iso_sp = norm.get("timestamp_iso_sao_paulo")

    origem_val = "bot" if (from_me and from_api) else ("human" if from_me else "whatsapp")
    if internal_only:
        origem_val = "internal"

    if from_me:
        if msg_status in ("", "sent"):
            status_val = "sent"
        elif msg_status in ("delivered", "read"):
            status_val = msg_status
        else:
            status_val = f"sent_{msg_status}" if msg_status else "sent"
    else:
        status_val = "received" if txt else "ignored_empty_text"

    if internal_only:
        status_val = "internal_saved"

    if not internal_only:
        try:
            telefone_chk = telefone
            if telefone_chk and is_blocked_number(telefone_chk):
                print(f">> [BLOCKED] Ignorando mensagem de número bloqueado: {telefone_chk}", flush=True)
                return None
        except Exception:
            pass

    row_in_full: Dict[str, Any] = {
        "telefone": telefone or None,
        "mensagem": {
            "text": txt,
            "raw": raw_payload,
            "meta": {
                "is_group": is_group,
                "group_id": group_id,
                "group_name": group_name,
                "sender_name": sender_name,
                "message_id": norm.get("message_id"),
                "instance_id": norm.get("instance_id"),
                "connected_phone": norm.get("connected_phone"),
                "chat_phone": norm.get("chat_phone") or telefone,
                "timestamp_iso_utc": ts_iso_utc,
                "timestamp_iso_sao_paulo": ts_iso_sp,
                "type": event_type,
                "status": msg_status,
            },
        },
        "nome": {"display": sender_name} if sender_name else None,
        "data": _now_iso(),
        "group_id": group_id,
        "group_name": group_name,
        "fromMe": from_me,
        "from_me": from_me,
        "direction": "out" if from_me else "in",
        "origem": origem_val,
        "ai_draft": None,
        "used_ai": False,
        "approval_mode": APPROVAL_MODE,
        "status": status_val,
    }

    if internal_only:
        try:
            row_in_full["mensagem"]["meta"]["internal"] = True
        except Exception:
            pass

    candidate_cols = [
        "telefone",
        "mensagem",
        "nome",
        "data",
        "group_id",
        "group_name",
        "fromMe",
        "from_me",
        "direction",
        "origem",
        "ai_draft",
        "used_ai",
        "approval_mode",
        "status",
        "message_id",
        "instance_id",
        "connected_phone",
    ]

    safe_row: Dict[str, Any] = {}
    for col in candidate_cols:
        if col in row_in_full and _column_exists(col):
            safe_row[col] = row_in_full[col]

    if not safe_row:
        if _column_exists("status"):
            safe_row["status"] = status_val
        if _column_exists("telefone"):
            safe_row["telefone"] = telefone
        if _column_exists("mensagem"):
            safe_row["mensagem"] = {"text": txt}
        if _column_exists("data"):
            safe_row["data"] = _now_iso()

    try:
        result = supabase.table(TABLE).insert(safe_row).execute()
        row = (result.data or [None])[0]
        if row:
            print(
                f">> [OK] Mensagem inserida. {ID_COLUMN}={row.get(ID_COLUMN)} tel={row.get('telefone')} "
                f"txt={txt[:60]!r} status={status_val} origem={origem_val}",
                flush=True,
            )
        return row
    except Exception as e:
        print(">> _save_in_supabase_from_zapi erro:", e, flush=True)
        return None


def _save_delivery_callback(
    payload: dict,
    *,
    parsed: Optional[dict] = None,
) -> Optional[dict]:
    """Persist DeliveryCallback events with raw payload for later auditing."""
    if not supabase:
        print(">> DELIVERY_CALLBACK: Supabase indisponível, registrando somente log.", flush=True)
        return None

    raw_payload = payload or {}
    try:
        norm = parsed if isinstance(parsed, dict) else parse_zapi_payload(raw_payload)
    except Exception as exc:
        print(">> DELIVERY_CALLBACK: falha ao normalizar payload:", exc, flush=True)
        norm = {}

    message_id = (norm.get("message_id") or raw_payload.get("messageId") or "").strip() or None
    status_candidates: Sequence[Any] = (
        norm.get("status"),
        raw_payload.get("status"),
        raw_payload.get("deliveryStatus"),
        raw_payload.get("error"),
        raw_payload.get("result"),
    )
    status_val = None
    for candidate in status_candidates:
        if isinstance(candidate, str) and candidate.strip():
            status_val = candidate.strip()
            break

    error_text = raw_payload.get("error")
    error_val = error_text.strip() if isinstance(error_text, str) else None
    telefone_norm = _digits_only(norm.get("telefone") or raw_payload.get("phone") or "")
    instance_id = norm.get("instance_id") or raw_payload.get("instanceId")

    now_iso = _now_iso()
    record: Dict[str, Any] = {
        "kind": "CALLBACK",
        "message_id": message_id,
        "status": status_val,
        "error": error_val,
        "phone": telefone_norm or None,
        "instance_id": instance_id,
        "raw_json": raw_payload,
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    data_clean = {k: v for k, v in record.items() if v is not None}

    try:
        response = supabase.table(DELIVERY_CALLBACKS_TABLE).insert(data_clean).execute()
    except Exception as exc:
        print(">> DELIVERY_CALLBACK: erro ao salvar:", exc, flush=True)
        return None

    saved_row = (response.data or [None])[0]
    return saved_row if isinstance(saved_row, dict) else None

def parse_zapi_payload(payload: dict) -> dict:
    p = payload or {}
    def _boolish(v) -> bool:
        if isinstance(v, bool): return v
        if v is None: return False
        s = str(v).strip().lower()
        return s in {"1", "true", "t", "yes", "y", "on", "sim"}
    chat_phone = str(p.get("phone") or "")
    is_group = (
        _boolish(p.get("isGroup"))
        or chat_phone.endswith("-group")
        or chat_phone.endswith("@g.us")
        or chat_phone == "status@broadcast"
    )
    group_id = (p.get("chatLid") or p.get("groupId")) if is_group else None
    group_name = p.get("chatName") if is_group else None
    telefone = chat_phone if not is_group else None
    # Heurística robusta para escolha do nome do remetente.
    # - Para conversas diretas (is_group == False) preferimos o `chatName` (normalmente o nome salvo no contato)
    #   ou campos de exibição (pushName/contactName/profileName). Só então usamos senderName ou name.
    # - Para grupos, preferimos o nome do participante (participantName) ou senderName.
    def _looks_like_phone(s: any) -> bool:
        try:
            if not s or not isinstance(s, str):
                return False
            ss = s.strip()
            # se contém '@' (ex: lid) ou termina com '-group', trata como não-nome
            if '@' in ss or ss.endswith('-group'):
                return True
            digits = sum(ch.isdigit() for ch in ss)
            if digits >= max(3, int(len(ss) * 0.6)):
                return True
            return False
        except Exception:
            return False

    def _first_nonempty(*fields):
        for f in fields:
            v = p.get(f)
            if isinstance(v, str) and v.strip():
                # ignore values that are clearly phone-like identifiers
                if _looks_like_phone(v):
                    continue
                return v.strip()
        return None

    if is_group:
        sender_name = _first_nonempty(
            "participantName", "senderName", "pushName", "name", "chatName", "contactName", "profileName"
        )
    else:
        sender_name = _first_nonempty(
            "chatName", "pushName", "contactName", "profileName", "participantName", "senderName", "name"
        )
    connected_phone = p.get("connectedPhone")
    message_id = p.get("messageId")
    instance_id = p.get("instanceId")
    ts_utc = _ts_ms_to_iso(p.get("momment"))
    ts_sp = ts_utc
    try:
        if ts_utc and ZoneInfo:
            dt_utc = datetime.fromisoformat(ts_utc)
            ts_sp = dt_utc.astimezone(ZoneInfo("America/Sao_Paulo")).isoformat()
    except Exception:
        pass
    txt = _extract_text_from_payload(p)
    from_me = _boolish(p.get("fromMe"))
    from_api = _boolish(p.get("fromApi") or p.get("fromAPI") or p.get("from_api"))
    etype = (p.get("type") or p.get("event") or "").strip()
    status = (p.get("status") or "").strip()
    return {
        "text": txt,
        "telefone": telefone,
        "raw_telefone": chat_phone,
        "is_group": is_group,
        "group_id": group_id,
        "group_name": group_name,
        "sender_name": sender_name,
        "chat_phone": chat_phone,
        "connected_phone": connected_phone,
        "message_id": message_id,
        "instance_id": instance_id,
        "timestamp_iso_utc": ts_utc,
        "timestamp_iso_sao_paulo": ts_sp,
        "fromMe": from_me,
        "fromApi": from_api,
        "type": etype,
        "status": status,
    }

def _chat_key_from_payload(p: dict) -> str:
    gid = (p.get("groupId") or p.get("chatLid") or "").strip()
    tel = (p.get("phone") or "").strip()
    return f"group:{gid}" if gid else f"phone:{tel}" if tel else "anon"

# =====================================================================
# Z-API helper (autoconfigurar webhooks)
# =====================================================================
def _zapi_update_webhooks(base_url: str, webhook_path: str = WEBHOOK_PATH) -> bool:
    # Validate required configuration
    if not (ZAPI_INSTANCE and ZAPI_TOKEN and ZAPI_CLIENT_TOKEN and base_url and base_url.startswith("https://")):
        print(">> Z-API: dados insuficientes p/ atualizar webhooks (precisa https + INSTANCE + ZAPI_TOKEN + ZAPI_CLIENT_TOKEN).", flush=True)
        return False

    target = f"{base_url.rstrip('/')}{webhook_path}"
    print(f">> Z-API: definindo webhook para {target}", flush=True)
    headers = {"Content-Type": "application/json", "Client-Token": ZAPI_CLIENT_TOKEN}
    notify = (ZAPI_WEBHOOK_MODE != "receive_only")

    endpoints: List[Tuple[str, Dict[str, Any]]] = [
        (f"{ZAPI_BASE.rstrip('/')}/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/update-every-webhooks", {"value": target, "notifySentByMe": notify}),
        (f"{ZAPI_BASE.rstrip('/')}/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/update-webhook-received", {"webhookUrl": target}),
    ]
    if notify:
        endpoints.append((f"{ZAPI_BASE.rstrip('/')}/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/update-webhook-received-delivery", {"webhookUrl": target}))

    ok_any = False
    last_status = None
    last_text = None

    start_time = time.time()
    max_total_seconds = 30.0  # don't block the caller for more than this
    attempt = 0

    for url, body in endpoints:
        attempt += 1
        # If we've exceeded the total grace window, abort early
        if time.time() - start_time > max_total_seconds:
            print(">> Z-API: tempo total excedido ao atualizar webhooks, abortando tentativas.", flush=True)
            break

        try:
            # use a modest per-request timeout to avoid long socket hangs
            r = requests.put(url, headers=headers, json=body, timeout=8)
            last_status = r.status_code
            last_text = (r.text or "")[:300]
            print(f">> webhook update TRY PUT {url} -> {r.status_code} {last_text}", flush=True)
            if 200 <= r.status_code < 300:
                ok_any = True
                break
            # If we get a non-2xx, wait a short backoff and try next endpoint
            time.sleep(min(2 ** (attempt - 1), 5))
        except KeyboardInterrupt:
            print(">> Z-API: interrupção pelo usuário durante update de webhook.", flush=True)
            return False
        except Exception as e:
            last_text = str(e)
            print(">> erro na tentativa de update webhook:", e, flush=True)
            # small backoff before next try
            try:
                time.sleep(min(2 ** (attempt - 1), 5))
            except Exception:
                pass

    if ok_any:
        print(f">> Webhook Z-API ajustado para: {target} (mode={'all' if notify else 'receive_only'})", flush=True)
    else:
        print(">> Falha ao atualizar webhook Z-API após tentativas. Última resposta:", last_status, last_text, flush=True)
    return ok_any

_last_webhook = {"target": None, "fail_count": 0, "next_retry": 0.0}

# ============================
# Finalizar ngrok
# ============================
def _kill_ngrok_windows() -> bool:
    try:
        r = subprocess.run(["taskkill", "/IM", "ngrok.exe", "/F"], capture_output=True, text=True)
        if r.returncode == 0:
            print(">> ngrok: processos finalizados (Windows).", flush=True)
            return True
        print(">> ngrok: nenhum processo para finalizar (Windows). Saída:", (r.stdout or r.stderr or "").strip(), flush=True)
        return False
    except Exception as e:
        print(">> ngrok (Windows):", e, flush=True)
        return False

def _kill_ngrok_posix() -> bool:
    ok = False
    try:
        r = subprocess.run(["pkill", "-f", "ngrok"], capture_output=True, text=True); ok = (r.returncode == 0) or ok
    except Exception:
        pass
    try:
        r2 = subprocess.run(["killall", "ngrok"], capture_output=True, text=True); ok = (r2.returncode == 0) or ok
    except Exception:
        pass
    print(">> ngrok:", "processos finalizados" if ok else "nenhum processo encontrado", flush=True)
    return ok

def kill_ngrok_processes() -> None:
    try:
        if platform.system().lower().startswith("win"):
            _kill_ngrok_windows()
        else:
            _kill_ngrok_posix()
        time.sleep(0.8)
    except Exception as e:
        print(">> ngrok: erro ao finalizar:", e, flush=True)

# ============================
# Captura URL pública do ngrok
# ============================
def _get_ngrok_public_url() -> Optional[str]:
    for api in ("http://127.0.0.1:4040/api/tunnels", "http://127.0.0.1:4041/api/tunnels"):
        try:
            r = requests.get(api, timeout=4)
            data = r.json() or {}
            for t in data.get("tunnels", []):
                pub = t.get("public_url") or ""
                if pub.startswith("https://"):
                    return pub
        except Exception:
            pass
    return None

# ============================
# Loop autoconfig webhook
# ============================
def _autoupdate_zapi_loop():
    while True:
        try:
            now = time.time()
            base = PUBLIC_BASE_URL or _get_ngrok_public_url()
            if not base:
                print(">> Nenhuma base URL pública disponível para webhook.", flush=True)
                time.sleep(ZAPI_AUTOCONFIG_INTERVAL or 30); continue
            target = f"{base.rstrip('/')}{WEBHOOK_PATH}"
            if now < _last_webhook.get("next_retry", 0):
                time.sleep(1); continue
            if target != _last_webhook.get("target"):
                ok = _zapi_update_webhooks(base, WEBHOOK_PATH)
                if ok:
                    _last_webhook["target"] = target
                    _last_webhook["fail_count"] = 0
                    _last_webhook["next_retry"] = 0
                else:
                    fc = int(_last_webhook.get("fail_count", 0)) + 1
                    _last_webhook["fail_count"] = fc
                    wait = min(300, 5 * (2 ** (fc - 1)))
                    _last_webhook["next_retry"] = now + wait
                    print(f">> Reagendando tentativa de webhook em ~{wait:.0f}s (fail_count={fc})", flush=True)
            time.sleep(ZAPI_AUTOCONFIG_INTERVAL)
        except Exception as e:
            print(">> autoupdate loop erro:", e, flush=True)
            time.sleep(ZAPI_AUTOCONFIG_INTERVAL)

# =====================================================================
# Assistants helpers
# =====================================================================
def _row_chat_key(row: dict) -> str:
    phone = str(row.get("telefone") or row.get("from") or "").strip()
    return f"phone:{phone}" if phone else f"anon:{row.get('id') or datetime.now().timestamp()}"

def _build_instructions_for_row(row: dict, history_block: Optional[str]) -> str:
    meta = (row.get("mensagem") or {}).get("meta") or {}
    is_group = bool(meta.get("is_group")) or bool(row.get("group_id"))
    group_name = str(row.get("group_name") or row.get("Group_name") or meta.get("group_name") or "").strip()
    telefone = str(row.get("telefone") or "").strip()
    sender_name = str(row.get("sender_name") or (row.get("nome") or {}).get("display", "") or "").strip()
    persona = _safe_selecionar_persona(is_group, group_name, sender_name)
    contexto = _safe_selecionar_contexto(row)
    partes: List[str] = []
    partes.append("[SYSTEM_RULES]\n" + SYSTEM_RULES)
    if PROMPT_DADOS:
        partes.append("[DADOS_DA_EMPRESA]\n" + PROMPT_DADOS)
    if PROMPT_POLITICAS:
        partes.append("[POLITICAS]\n" + PROMPT_POLITICAS)
    if persona:
        partes.append("[PERSONA]\n" + json.dumps(persona, ensure_ascii=False))
    if contexto:
        partes.append("[CONTEXTO_SEL]\n" + json.dumps(contexto, ensure_ascii=False))
    if is_group and group_name:
        partes.append(f"[CHAT]\nConversa de grupo: {group_name}.")
    elif telefone:
        partes.append(f"[CHAT]\nConversa individual com o número: {telefone}.")
    if history_block:
        partes.append("[HISTORICO]\n" + history_block)
    human_examples: List[str] = []
    try:
        if telefone:
            for sug in _fetch_human_suggestions(telefone, limit=3):
                cliente = (sug.get("client_excerpt") or "(sem trecho registrado)").strip()
                resposta = (sug.get("text") or "").strip()
                if not resposta:
                    continue
                human_examples.append(f"Cliente: {cliente}\nEquipe Lucenera: {resposta}")
    except Exception as _e_sug:
        print(">> aviso: falha ao carregar sugestões humanas:", _e_sug, flush=True)
    if human_examples:
        partes.append("[EXEMPLOS_HUMANOS]\nHistórico de respostas reais da equipe:\n\n" + "\n\n".join(human_examples))
    # If the incoming message is an image description (generated earlier), make it explicit
    try:
        msg_text = (row.get("mensagem") or {}).get("text") or ""
        if isinstance(msg_text, str) and msg_text.strip().startswith("[Imagem]"):
            partes.append(
                "[MEDIA]\nO cliente enviou uma imagem. Abaixo está a descrição gerada automaticamente da imagem:\n"
                + msg_text.strip()
                + "\nUse essa descrição como base para sua resposta."
            )
    except Exception:
        pass
    partes.append(
        "[REGRAS]\n- Use dados reais quando disponíveis; não invente.\n"
        "- Se faltar UM dado essencial, faça só 1 pergunta objetiva.\n"
        "- Responda curto (WhatsApp)."
    )
    # Instrução adicional: solicitar que a IA gere um JSON com duas saídas
    partes.append(
        "[OUTPUT]\nAlém da resposta ao cliente, gere também uma segunda saída chamada 'mensagem_setor'. "
        "Essa mensagem deve ser um texto objetivo explicando o que o setor responsável (Admin ou Estoque) deve fazer com base na mensagem original. "
        "O formato esperado é um JSON com dois campos:\n{\n  \"resposta_cliente\": \"...\",\n  \"mensagem_setor\": \"...\"\n}\n"
        "Se não houver ação clara para setor, deixe o campo 'mensagem_setor' vazio."
    )
    return "\n\n".join(partes)


def _extract_json_outputs_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Tenta extrair um objeto JSON do texto e retornar (resposta_cliente, mensagem_setor).
    Procura o primeiro JSON válido que começar em '{' e devolve os campos se encontrados.
    """
    if not text or not isinstance(text, str):
        return (None, None)
    import json
    s = text.strip()
    # procurar primeiro '{'
    start = s.find('{')
    if start == -1:
        return (None, None)
    depth = 0
    for i in range(start, len(s)):
        ch = s[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                candidate = s[start:i+1]
                try:
                    obj = json.loads(candidate)
                    if isinstance(obj, dict):
                        rc = obj.get('resposta_cliente') or obj.get('resposta') or obj.get('response')
                        ms = obj.get('mensagem_setor') or obj.get('mensagem_setor_text') or obj.get('mensagem_setor')
                        return (rc, ms)
                except Exception:
                    # continua procurando caso haja outro bloco JSON
                    pass
    return (None, None)

def _formatar_resposta_julia_local(texto: str) -> str:
    s = (texto or "").strip()
    if not s:
        return ""
    s = re.sub(r"^\s*j[uú]lia\.?\s*-?\s*", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"\s{2,}", " ", s)
    s = s.rstrip(" !")
    return f"Julia. {s}"

def _gentle_greeting_reply(incoming_text: str, sender_name: str | None) -> str:
    """
    Gera uma resposta curta e natural para cumprimentos / smalltalk.
    Evita frases robotizadas como "Recebi sua mensagem" e prefere tom humano e prestativo.
    """
    name = (sender_name or "").strip()
    # Se não tivermos nome, usar uma forma neutra
    if name:
        # Mantém curta e direta
        return f"Oi {name}! Tudo bem? Aqui é a Julia — estou por aqui se precisar. Quer que eu já verifique algo pra você?"
    else:
        return "Oi! Tudo bem? Aqui é a Julia — estou por aqui se precisar. Quer que eu já verifique algo pra você?"

# Campos que não devem ser sobrescritos no Supabase
NON_WRITABLE_COLS = {"is_group"}

def _supabase_update_safe(row_id: Any, patch: Dict[str, Any]) -> None:
    try:
        if not supabase or not isinstance(patch, dict):
            return
        safe = {k: v for k, v in patch.items() if k not in NON_WRITABLE_COLS and _column_exists(k)}
        if not safe:
            print(">> _supabase_update_safe: nada para atualizar.")
            return
        supabase.table(TABLE).update(safe).eq(ID_COLUMN, row_id).execute()
    except Exception as e:
        print(">> _supabase_update_safe erro:", e, flush=True)


def _record_human_suggestion(
    *,
    telefone: Optional[str],
    texto: str,
    group_id: Optional[str] = None,
    client_row: Optional[dict] = None,
    source: str = "admin",
    author: Optional[str] = None,
    reply_to: Optional[Any] = None,
) -> None:
    if not supabase or not texto.strip():
        return

    telefone = (telefone or "").strip()
    group_id = (group_id or "").strip() or None

    client_excerpt = ""
    if client_row:
        try:
            base_msg = (client_row.get("mensagem") or {}).get("text") or ""
            client_excerpt = (base_msg or "").strip()[:220]
        except Exception:
            client_excerpt = ""
        telefone = telefone or (client_row.get("telefone") or "").strip()
        group_id = group_id or client_row.get("group_id")

    meta = {
        "type": "human_suggestion",
        "source": source,
    }
    if reply_to is not None:
        meta["reply_to"] = reply_to
    if client_excerpt:
        meta["client_excerpt"] = client_excerpt
    if author:
        meta["author"] = author

    payload = {
        "telefone": telefone or None,
        "group_id": group_id or None,
        "mensagem": {"text": texto.strip(), "meta": meta},
        "fromMe": True,
        "from_me": True,
        "direction": "out",
        "origem": "human_suggestion",
        "status": "suggested",
        "used_ai": False,
        "data": _now_iso(),
    }

    safe_payload = {}
    for key, value in payload.items():
        if _column_exists(key):
            safe_payload[key] = value

    if "mensagem" not in safe_payload and _column_exists("mensagem"):
        safe_payload["mensagem"] = payload["mensagem"]

    try:
        supabase.table(TABLE).insert(safe_payload).execute()
        print(
            f">> [HUMAN_SUGGESTION] Registrada sugestão ({source}) tel={telefone or group_id}",
            flush=True,
        )
    except Exception as e:
        print(">> aviso: falha ao registrar sugestão humana:", e, flush=True)

_COLUMN_EXISTS_CACHE: Dict[str, bool] = {}
_COLUMN_EXISTS_FALLBACK = {
    "id", "id_num", "telefone", "mensagem", "status", "ai_draft", "used_ai",
    "approval_mode", "data", "group_id", "group_name", "nome", "origem",
    "final_out", "approved", "error", "thread_id", "analysis", "fromMe",
    "manual_reply", "approved_by", "message_id", "instance_id", "connected_phone",
    "is_group",
}


def _column_exists(colname: str) -> bool:
    """Best-effort check for Supabase columns with cache and safe fallback."""
    name = (colname or "").strip()
    if not name:
        return False

    cached = _COLUMN_EXISTS_CACHE.get(name)
    if cached is not None:
        return cached

    exists = not supabase  # assume True when Supabase indisponível
    try:
        if supabase and _supabase_column_exists:
            exists = bool(_supabase_column_exists(TABLE, name))
        elif supabase:
            exists = name in _COLUMN_EXISTS_FALLBACK
        # when supabase is None, keep exists=True (fail-open as antes)
    except Exception:
        exists = name in _COLUMN_EXISTS_FALLBACK if supabase else True

    _COLUMN_EXISTS_CACHE[name] = exists
    return exists


def _supabase_update_safe(row_id: Any, patch: Dict[str, Any]) -> None:
    try:
        if not supabase or not isinstance(patch, dict):
            return
        safe = {k: v for k, v in patch.items() if k not in NON_WRITABLE_COLS and _column_exists(k)}
        if not safe:
            print(">> _supabase_update_safe: nada para atualizar.")
            return
        supabase.table(TABLE).update(safe).eq(ID_COLUMN, row_id).execute()
    except Exception as e:
        print(">> _supabase_update_safe erro:", e, flush=True)

# =====================================================================
# TEAMS — helpers
# =====================================================================
def _effective_base_url() -> str:
    """
    Retorna a URL pública que deve ser usada em links enviados por Teams/cards.
    Preferência: PUBLIC_BASE_URL -> ngrok public url -> localhost fallback.
    """
    try:
        # 1) explicit env override
        if PUBLIC_BASE_URL:
            return PUBLIC_BASE_URL

        # 2) persisted last-known public base saved between runs
        persisted = _load_persisted_public_base()
        if persisted:
            return persisted

        # 3) try to read live from ngrok API
        live = _get_ngrok_public_url()
        if live:
            # persist for next runs (but only when no explicit PUBLIC_BASE_URL)
            try:
                _persist_public_base(live)
            except Exception:
                pass
            return live
    except Exception:
        pass
    # 4) fallback localhost
    return f"http://127.0.0.1:{PORT}"


def _persist_public_base(url: str) -> None:
    """Persiste a última URL pública detectada em disco para uso entre reinícios."""
    try:
        p = os.path.join(BASE_DIR, ".last_public_base")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(str(url).strip())
    except Exception:
        pass


def _load_persisted_public_base() -> Optional[str]:
    try:
        p = os.path.join(BASE_DIR, ".last_public_base")
        if not os.path.exists(p):
            return None
        with open(p, "r", encoding="utf-8") as fh:
            v = fh.read().strip()
            return v or None
    except Exception:
        return None


def _validate_persisted_public_base() -> None:
    """Valida a URL persistida no boot.

    Estratégia:
    - Se não houver arquivo persistido, nada a fazer.
    - Se `PUBLIC_BASE_URL` estiver definido e igual ao persistido, mantém.
    - Tenta verificar se o persisted responde em /ping (timeout curto).
    - Se ngrok estiver ativo e a URL live do ngrok for igual ao persistido, mantém.
    - Caso contrário, remove o arquivo persistido para forçar re-detectar.
    """
    try:
        persisted = _load_persisted_public_base()
        if not persisted:
            return
        # If explicit env overrides and matches persisted, keep
        if PUBLIC_BASE_URL and str(PUBLIC_BASE_URL).strip() == str(persisted).strip():
            return

        # Try quick ping to persisted/ping
        try:
            ping_url = persisted.rstrip("/") + "/ping"
            r = requests.get(ping_url, timeout=2)
            if 200 <= r.status_code < 300:
                # consider valid
                return
        except Exception:
            pass

        # If ngrok is running and its current public url matches persisted, keep
        try:
            live = _get_ngrok_public_url()
            if live and live.rstrip("/") == str(persisted).rstrip("/"):
                return
        except Exception:
            pass

        # Otherwise remove persisted file to force re-detect
        try:
            p = os.path.join(BASE_DIR, ".last_public_base")
            if os.path.exists(p):
                os.unlink(p)
                print(
                    f">> .last_public_base removido porque parece inválido ou desatualizado: {persisted}",
                    flush=True,
                )
        except Exception:
            pass
    except Exception:
        pass

def _is_group_row(row: dict) -> bool:
    if not isinstance(row, dict):
        return False
    if row.get("group_id"):
        return True
    meta = (row.get("mensagem") or {}).get("meta") or {}
    if bool(meta.get("is_group")):
        return True
    gname = (row.get("group_name") or row.get("Group_name") or meta.get("group_name") or "").strip()
    return bool(gname)


def _is_blocked_row(row: dict) -> bool:
    try:
        status = (row.get("status") or "").lower()
        if status == "ignored_blocked":
            return True
    except Exception:
        pass
    try:
        tel = (row.get("telefone") or "")
        if tel and is_blocked_number(tel):
            return True
    except Exception:
        pass
    return False

def _teams_post_card(title: str, text: str, buttons: List[Dict[str, str]] | None = None, color: str = "0078D7", channel: str | None = None) -> bool:
    """
    Envia um card simples para o Teams usando um webhook.

    Hoje: monta um payload do tipo MessageCard com `title`, `text`, `themeColor` e
    possíveis `buttons`, e faz um POST para `TEAMS_WEBHOOK_URL`.
    Aqui adicionamos o parâmetro opcional `channel` para permitir rotear o
    card para webhooks alternativos (admin/estoque). Se `channel` for None,
    o comportamento antigo permanece (usa `TEAMS_WEBHOOK_URL`).
    """
    # resolve webhook a usar (mantém compatibilidade com comportamento atual)
    webhook_url = get_teams_webhook_for_channel(channel) or (TEAMS_WEBHOOK_URL or None)
    if not webhook_url:
        return False
    # Se a mensagem for de saída (fromMe) ou for um registro de outgoing, não postar no Teams
    try:
        # tenta extrair a linha se for passada como dict inserida diretamente
        if isinstance(text, dict):
            row_candidate = text
        else:
            row_candidate = None
    except Exception:
        row_candidate = None
    try:
        meta = (row_candidate or {}).get("mensagem", {}).get("meta", {}) if row_candidate else {}
        if (row_candidate and (bool(row_candidate.get("fromMe") or (row_candidate.get("origem") or "").lower() in {"bot","human"} or str(meta.get("type") or "").lower().startswith("outgoing")))):
            return False
    except Exception:
        pass
    # Não enviar se for número bloqueado
    try:
        status = (row_candidate or {}).get("status") if row_candidate else ""
        if isinstance(status, str) and status.lower() == "ignored_blocked":
            print(f">> [TEAMS] Não enviar notificação para número bloqueado (status) : {row_candidate.get('telefone')}", flush=True)
            return False
    except Exception:
        pass
    try:
        telc = (row_candidate or {}).get("telefone") if row_candidate else ""
        if telc and is_blocked_number(telc):
            print(f">> [TEAMS] Não enviar notificação para número bloqueado: {telc}", flush=True)
            return False
    except Exception:
        pass
    payload: Dict[str, Any] = {
        "@type": "MessageCard","@context": "https://schema.org/extensions",
        "summary": title,"title": title,"text": text,"themeColor": color,
    }
    if buttons:
        payload["potentialAction"] = [{"@type": "OpenUri","name": b["name"],"targets": [{"os": "default", "uri": b["url"]}]} for b in buttons]
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        ok = 200 <= r.status_code < 300
        print(f">> TEAMS post -> {r.status_code} {r.text[:200]}", flush=True)
        return ok
    except Exception as e:
        print(">> TEAMS erro:", e, flush=True)
        return False


def _notify_delivery_teams(event_type: str, payload: Dict[str, Any]) -> None:
    webhook = TEAMS_WEBHOOK_ENTREGAS or TEAMS_WEBHOOK_ADMIN or TEAMS_WEBHOOK_URL
    if not webhook:
        print(f"DELIVERY_TEAMS_FAIL event={event_type} reason=missing_webhook", flush=True)
        return

    if event_type == "start":
        text = f"📦 Inicio confirmacao de entrega - phone: {payload.get('phone') or '-'}"
    elif event_type == "finish":
        codigo_projeto_raw = payload.get("codigo_projeto") or payload.get("obra_codigo") or payload.get("projeto_numero") or ""
        recebedor_raw = payload.get("recebedor") or payload.get("recebedor_nome") or ""
        observacao_raw = payload.get("observacao") or payload.get("obs") or ""
        foto_url_raw = payload.get("url") or payload.get("foto_url") or ""

        codigo_projeto = str(codigo_projeto_raw).strip() or "-"
        recebedor = str(recebedor_raw).strip() or "-"
        obs = str(observacao_raw).strip()
        foto_url = str(foto_url_raw).strip()

        message = f"✅ Entrega finalizada - Projeto: {codigo_projeto} | Recebedor: {recebedor}"
        if obs and obs != "-":
            message += f" | Obs: {obs}"
        if foto_url:
            message += f" | Foto: {foto_url}"
        text = message
    else:
        text = f"Delivery event {event_type}: {payload}"

    body = {"text": text}
    try:
        resp = requests.post(webhook, json=body, timeout=8)
        if 200 <= resp.status_code < 300:
            print(f"DELIVERY_TEAMS_SENT event={event_type} status={resp.status_code}", flush=True)
        else:
            print(
                f"DELIVERY_TEAMS_FAIL event={event_type} status={resp.status_code} body={resp.text[:120]}",
                flush=True,
            )
    except Exception as exc:
        print(f"DELIVERY_TEAMS_FAIL event={event_type} error={exc}", flush=True)

def _teams_format_text(row: dict) -> str:
    nome = ((row.get("nome") or {}).get("display") or row.get("sender_name") or "—").strip()
    tel  = (row.get("telefone") or "—")
    meta = (row.get("mensagem") or {}).get("meta") or {}

    # preferir o preview do debounce, se presente
    preview = meta.get("debounce_batch_preview")
    batch_s = meta.get("debounce_batch_seconds")
    batch_n = meta.get("debounce_batch_count")

    if preview:
        header = []
        if batch_s: header.append(f"{batch_s}s")
        if batch_n: header.append(f"{batch_n} msgs")
        prefix = f"({', '.join(header)}) " if header else ""
        msg = f"{prefix}{preview}"
    else:
        msg = ((row.get("mensagem") or {}).get("text") or "").strip()

    return f"👤 **Nome:** {nome}\n📞 **Telefone:** {tel}\n🛎️ **Mensagem:** {msg}"


def _teams_notify(row: dict, suggested: str, route: str | None, channel: str | None = None) -> None:
    # Não notificar se for grupo
    if _is_group_row(row):
        print(">> [TEAMS] skip notify (grupo).", flush=True)
        return
        if _is_blocked_row(row):
            print(f">> [TEAMS] skip notify (blocked) for {row.get('telefone')}", flush=True)
            return
    # Não notificar se a mensagem é de saída (registrada como enviado pelo time)
    try:
        if isinstance(row, dict) and row.get("__entrega_flow__") is True:
            print(">> [TEAMS] aprovação ignorada (fluxo entregas).", flush=True)
            return
    except Exception:
        pass
    try:
        telefone_raw = row.get("telefone") if isinstance(row, dict) else None
        telefone_norm = _digits_only(telefone_raw)
        mensagem_bruta = ""
        msg_payload = row.get("mensagem") if isinstance(row, dict) else None
        if isinstance(msg_payload, dict):
            mensagem_bruta = (
                msg_payload.get("text")
                or msg_payload.get("body")
                or msg_payload.get("message")
                or ""
            )
        elif isinstance(msg_payload, str):
            mensagem_bruta = msg_payload
        gatilho = (mensagem_bruta or "").strip().strip('"').strip("'").lower()
        if telefone_norm and telefone_norm in ENTREGADORES_WHATS and "entrega finalizada" in gatilho:
            print(">> [TEAMS] aprovação ignorada (entrega finalizada por entregador).", flush=True)
            return
    except Exception:
        pass
    try:
        meta = (row.get("mensagem") or {}).get("meta") or {}
        if bool(row.get("fromMe")) or (str(row.get("origem") or "").lower() in {"bot","human"} and str(meta.get("type") or "").lower().startswith("outgoing")):
            print("-> [TEAMS] skip notify (outgoing/fromMe).", flush=True)
            return
    except Exception:
        pass

    # mantém compatibilidade: se `channel` for None, usa o webhook padrão
    if channel:
        webhook_resolved = get_teams_webhook_for_channel(channel)
        if not webhook_resolved:
            print(f"[TEAMS] Nenhum webhook configurado para o canal: {channel}", flush=True)
            return
    else:
        if not TEAMS_WEBHOOK_URL:
            return
    rid = row.get(ID_COLUMN) or row.get("id")
    base = _effective_base_url()
    search_q = row.get("telefone") or str(rid)
    approve = f"{base}/teams/approve?id={rid}&token={TEAMS_ACTION_TOKEN}"
    reject  = f"{base}/teams/reject?id={rid}&token={TEAMS_ACTION_TOKEN}"
    admin   = f"{base}/admin?q={search_q}"
    # link para sugerir resposta via formulário seguro (/teams/suggest)
    suggest = f"{base}/teams/suggest?id={rid}&token={TEAMS_ACTION_TOKEN}"
    extra = ""
    if route == "admin":
        extra = "\n\n📣 **Interno:** acionar Vinícius (assunto administrativo/financeiro)."
    elif route == "log":
        extra = "\n\n📣 **Interno:** acionar Matheus (estoque/entrega/logística)."
    text = _teams_format_text(row) + f"\n\n🤖 **Sugerida:** {suggested}{extra}"
    _teams_post_card(
        title="✅ Aprovação necessária — Lucenera",
        text=text,
        buttons=[
            {"name": "✓ Aprovar", "url": approve},
            {"name": "✗ Rejeitar", "url": reject},
            {"name": "Sugerir resposta", "url": suggest},
            {"name": "Abrir painel", "url": admin},
        ],
        channel=channel,
    )

def _teams_format_text(row: dict) -> str:
    nome = ((row.get("nome") or {}).get("display") or row.get("sender_name") or "—").strip()
    tel  = (row.get("telefone") or "—")
    meta = (row.get("mensagem") or {}).get("meta") or {}

    # preferir o preview do debounce, se presente
    preview = meta.get("debounce_batch_preview")
    batch_s = meta.get("debounce_batch_seconds")
    batch_n = meta.get("debounce_batch_count")

    if preview:
        header = []
        if batch_s: header.append(f"{batch_s}s")
        if batch_n: header.append(f"{batch_n} msgs")
        prefix = f"({', '.join(header)}) " if header else ""
        msg = f"{prefix}{preview}"
    else:
        msg = ((row.get("mensagem") or {}).get("text") or "").strip()

    return f"👤 **Nome:** {nome}\n📞 **Telefone:** {tel}\n🛎️ **Mensagem:** {msg}"


def _teams_notify(row: dict, suggested: str, route: str | None, channel: str | None = None) -> None:
    if _is_group_row(row):
        print(">> [TEAMS] skip notify (grupo).", flush=True)
        return
        if _is_blocked_row(row):
            print(f">> [TEAMS] skip notify (blocked) for {row.get('telefone')}", flush=True)
            return
    # Não notificar se a mensagem é de saída (registrada como enviado pelo time)
    try:
        if isinstance(row, dict) and row.get("__entrega_flow__") is True:
            print(">> [TEAMS] aprovação ignorada (fluxo entregas).", flush=True)
            return
    except Exception:
        pass
    try:
        telefone_raw = row.get("telefone") if isinstance(row, dict) else None
        telefone_norm = _digits_only(telefone_raw)
        mensagem_bruta = ""
        msg_payload = row.get("mensagem") if isinstance(row, dict) else None
        if isinstance(msg_payload, dict):
            mensagem_bruta = (
                msg_payload.get("text")
                or msg_payload.get("body")
                or msg_payload.get("message")
                or ""
            )
        elif isinstance(msg_payload, str):
            mensagem_bruta = msg_payload
        gatilho = (mensagem_bruta or "").strip().strip('"').strip("'").lower()
        if telefone_norm and telefone_norm in ENTREGADORES_WHATS and "entrega finalizada" in gatilho:
            print(">> [TEAMS] aprovação ignorada (entrega finalizada por entregador).", flush=True)
            return
    except Exception:
        pass
    try:
        meta = (row.get("mensagem") or {}).get("meta") or {}
        if bool(row.get("fromMe")) or (str(row.get("origem") or "").lower() in {"bot","human"} and str(meta.get("type") or "").lower().startswith("outgoing")):
            print("-> [TEAMS] skip notify (outgoing/fromMe).", flush=True)
            return
    except Exception:
        pass
    # mantém compatibilidade: se `channel` for None, usa o webhook padrão
    if channel:
        webhook_resolved = get_teams_webhook_for_channel(channel)
        if not webhook_resolved:
            print(f"[TEAMS] Nenhum webhook configurado para o canal: {channel}", flush=True)
            return
    else:
        if not TEAMS_WEBHOOK_URL:
            return

    rid = row.get(ID_COLUMN) or row.get("id")
    base = _effective_base_url()
    search_q = row.get("telefone") or str(rid)

    approve = f"{base}/teams/approve?id={rid}&token={TEAMS_ACTION_TOKEN}"
    reject  = f"{base}/teams/reject?id={rid}&token={TEAMS_ACTION_TOKEN}"
    admin   = f"{base}/admin?q={search_q}"
    # atalho para abrir o painel já filtrado para o contato, visando escrever uma resposta manual
    # use /teams/suggest so the card opens the suggest form that posts to /teams/suggest
    suggest = f"{base}/teams/suggest?id={rid}&token={TEAMS_ACTION_TOKEN}"

    extra = ""
    if route == "admin":
        extra = "\n\n📣 **Interno:** acionar Vinícius (assunto administrativo/financeiro)."
    elif route == "log":
        extra = "\n\n📣 **Interno:** acionar Matheus (estoque/entrega/logística)."

    text = _teams_format_text(row) + f"\n\n🤖 **Sugerida:** {suggested}{extra}"

    _teams_post_card(
        title="✅ Aprovação necessária — Lucenera",
        text=text,
        buttons=[
            {"name": "✓ Aprovar", "url": approve},
            {"name": "✗ Rejeitar", "url": reject},
            {"name": "Sugerir resposta", "url": suggest},
            {"name": "Abrir painel", "url": admin},
        ],
        channel=channel,
    )


def _teams_notify_log(row: dict, title: str, status_tag: str, note: str | None = None, channel: str | None = None) -> None:
    if _is_group_row(row):
        print(f">> [TEAMS] skip log (grupo) — {status_tag}", flush=True)
        return
    if _is_blocked_row(row):
        print(f">> [TEAMS] skip log (blocked) — {status_tag} for {row.get('telefone')}", flush=True)
        return
    # mantém compatibilidade: se `channel` for None, usa o webhook padrão
    if channel:
        webhook_resolved = get_teams_webhook_for_channel(channel)
        if not webhook_resolved:
            print(f"[TEAMS] Nenhum webhook configurado para o canal: {channel}", flush=True)
            return
    else:
        if not TEAMS_WEBHOOK_URL:
            return
    # Não postar logs de mensagens de saída (fromMe/outgoing)
    try:
        meta = (row.get("mensagem") or {}).get("meta") or {}
        if bool(row.get("fromMe")) or (str(row.get("origem") or "").lower() in {"bot","human"} and str(meta.get("type") or "").lower().startswith("outgoing")):
            print(f">> [TEAMS] skip log (outgoing/fromMe) — {status_tag}", flush=True)
            return
    except Exception:
        pass

    base = _effective_base_url()
    search_q = row.get("telefone") or ""
    admin = f"{base}/admin?q={search_q}"
    suggest = f"{base}/admin?q={search_q}&compose=1"

    text = _teams_format_text(row) + f"\n\n🪪 **Status:** {status_tag}"
    if note:
        text += f"\n\n📝 {note}"

    _teams_post_card(
        title=title,
        text=text,
        buttons=[
            {"name": "Sugerir resposta", "url": suggest},
            {"name": "Abrir painel", "url": admin},
        ],
        color="888888",
        channel=channel,
    )


def _montar_mensagem_setor_detalhada(
    row: dict,
    suggested: str | None,
    setor: str,
    history_lines: Optional[List[str]] = None,
) -> tuple[str, str]:
    """
    Monta uma mensagem textual detalhada para o setor (`admin` ou `estoque`).
    Retorna (title, text) prontos para enviar via `_teams_post_card`.
    """
    nome = ((row.get("nome") or {}).get("display") or row.get("sender_name") or "—").strip()
    telefone = (row.get("telefone") or "—")
    mensagem_original = ((row.get("mensagem") or {}).get("text") or "").strip()

    # mapa legível para título e rótulo do setor
    setor_label = "Estoque" if setor == "estoque" else ("Admin" if setor == "admin" else setor.capitalize())
    interno = ""
    if setor == "estoque":
        interno = "📣 Interno: acionar Matheus (estoque/entrega/logística)."
    elif setor == "admin":
        interno = "📣 Interno: acionar Vinícius (assunto administrativo/financeiro)."

    # tenta obter histórico resumido para enriquecer o bloco "Resumo para o SETOR"
    history_lines = list(history_lines or [])
    if not history_lines:
        try:
            history_lines = _collect_history_for_routing(row, limit=6)
        except Exception:
            history_lines = []
    resumo_contexto = history_lines[-3:] if history_lines else []

    analysis_text = _analysis_to_text(row.get("analysis"))
    contexto_norm = _norm(" ".join(filter(None, [mensagem_original] + history_lines + [analysis_text])))
    numeros_contexto = _extract_numeric_tokens(contexto_norm)

    finance_intent = extrair_intencao_financeiro(
        mensagem_original,
        history_lines=history_lines,
        analysis_text=analysis_text,
    )
    estoque_intent = extrair_intencao_estoque(
        mensagem_original,
        history_lines=history_lines,
        analysis_text=analysis_text,
    )

    # construir bloco de cabeçalho com os dados principais
    header_lines = [
        "✅ Aprovação necessária — Lucenera",
        f"👤 Nome: {nome}",
        f"📞 Telefone: {telefone}",
        f"🛎️ Mensagem: {mensagem_original}",
    ]
    if suggested:
        header_lines.append(f"\n🤖 Sugerida: {suggested}")
    if interno:
        header_lines.append(f"\n{interno}")

    # montar o resumo/instrução para o setor
    resumo_lines = []
    if setor == "estoque":
        resumo_lines.append("Resumo para o ESTOQUE:")
        if not estoque_intent:
            resumo_lines.append("- Conteúdo não parece logístico; revisar manualmente antes de acionar o time.")
        else:
            has_entrega = any(token in contexto_norm for token in ("entrega", "entregar", "entregas", "retirada", "coleta"))
            has_material = "separar material" in contexto_norm or "separacao" in contexto_norm
            has_nf = any(token in contexto_norm for token in ("nf de remessa", "nota fiscal de remessa", "nota de remessa", "remessa"))
            has_horario = any(token in contexto_norm for token in ("horario", "hora", "endereco", "local", "rua"))

            if has_entrega:
                resumo_lines.append("- Confirmar entrega ou retirada mencionada e alinhar data/horário com o cliente.")
            else:
                resumo_lines.append("- Confirmar se há entrega pendente e combinar data/horário quando necessário.")

            if has_material:
                resumo_lines.append("- Separar o material solicitado conforme indicado na conversa.")

            if has_nf:
                resumo_lines.append("- Verificar necessidade de NF de remessa e providenciar emissão." )
            else:
                resumo_lines.append("- Verificar se é necessário emitir NF de remessa para o movimento.")

            if has_horario or has_entrega:
                resumo_lines.append("- Registrar no sistema horário e endereço da entrega/retirada (se fornecidos).")
    elif setor == "admin":
        resumo_lines.append("Resumo para o ADMINISTRATIVO/FINANCEIRO:")
        payment_detail = None
        if "sinal" in contexto_norm or "entrada" in contexto_norm or "parcela" in contexto_norm:
            if numeros_contexto:
                payment_detail = f"valores citados: {' + '.join(numeros_contexto[:3])}" 
            else:
                payment_detail = "sinal mencionado pelo cliente"
        if payment_detail:
            resumo_lines.append(f"- Verificar forma de pagamento acordada ({payment_detail}).")
        else:
            resumo_lines.append("- Verificar forma de pagamento acordada com o cliente.")

        has_contrato = any(token in contexto_norm for token in ("contrato", "pedid", "condicao", "condicoes", "proposta"))
        if has_contrato:
            resumo_lines.append("- Validar contrato, pedido e condições combinadas descritas na conversa.")
        else:
            resumo_lines.append("- Validar contrato, pedido e condições combinadas (se aplicável).")

        has_nf = any(token in contexto_norm for token in ("nota fiscal", "nf", "nfe", "faturamento"))
        if has_nf:
            resumo_lines.append("- Confirmar emissão de nota fiscal correta e encaminhar ao cliente." )
        else:
            resumo_lines.append("- Confirmar emissão de nota fiscal correta quando necessário.")

        resumo_lines.append("- Registrar a condição negociada no sistema interno.")
    else:
        resumo_lines.append(f"Resumo para o {setor_label}:")
        resumo_lines.append("Rever mensagem e agir conforme procedimento padrão.")

    # incluir contexto histórico, se houver
    if resumo_contexto:
        resumo_lines.append("\nCom base nas mensagens e no histórico:")
        resumo_lines.extend(resumo_contexto)

    # juntar tudo em um texto coerente
    title = f"Resumo para {setor_label} — Lucenera"
    texto_setor = "\n".join(header_lines) + "\n\n" + "\n".join(resumo_lines)
    return title, texto_setor

# =====================================================================
# PROCESSAMENTO INLINE (mantido e corrigido)
# =====================================================================
def processar_inline(row: dict) -> None:
    """
    Fluxo DM-only (apenas conversas diretas) com portão de contexto.
    Sempre passa pela IA (até 'oi'), mas só carrega histórico quando fizer sentido.
    """
    if not supabase:
        return

    try:
        if is_internal_message(row):
            logging.info(
                "[INTERNAL] processar_inline chamado para mensagem interna; ignorando. tel=%s",
                (row.get("telefone") or row.get("phone") or ""),
            )
            return
    except Exception as _e_internal_gate:
        print(">> aviso: falha ao avaliar is_internal_message em processar_inline:", _e_internal_gate, flush=True)

    # proteção: não processar IA para mensagens enviadas pela empresa
    try:
        if _row_is_from_me(row):
            print("[IA] Ignorando mensagem from_me=True (empresa) em processar_inline.", flush=True)
            return
    except Exception as e:
        # fallback defensivo: nunca derrubar o app por causa desse check
        print(f"[IA] Erro em _row_is_from_me, ignorando gate: {e}", flush=True)

    # Proteção extra: abortar se número bloqueado (status ou lista)
    try:
        st = (row.get("status") or "").lower()
        telc = (row.get("telefone") or "")
        if st == "ignored_blocked" or (telc and is_blocked_number(telc)):
            print(f"[BLOCKED] processar_inline chamado para número bloqueado; abortando. Tel: {telc}", flush=True)
            return
    except Exception:
        pass

    try:
        history_lines = _collect_history_for_routing(row, limit=8)
    except Exception:
        history_lines = []

    # ---------------- helpers ----------------
    def _now_ts() -> float:
        import time as _t
        return _t.time()

    def _safe_is_greeting(texto: str) -> bool:
        try:
            return is_greeting(texto)
        except NameError:
            t = (texto or "").strip().lower()
            return t in {"oi","olá","ola","e ai","eai","tudo bem","td bem","bom dia","boa tarde","boa noite"}

    def _safe_is_followup(texto: str) -> bool:
        try:
            return is_followup(texto)
        except NameError:
            t = (texto or "").lower()
            return any(p in t for p in ["deu certo","como ficou","e aí","e ai","conseguiu","e sobre"])

    def _safe_is_logistica(texto: str) -> bool:
        try:
            return is_logistica(texto)
        except NameError:
            t = (texto or "").lower()
            return any(p in t for p in [
                "entrega","prazo","rastre","instala","retirada","nota fiscal","nf",
                "troca","devolu","garantia","led","driver","spot","luminaria","luminária"
            ])

    def _safe_is_blocked_number(tel: str) -> bool:
        """Checa bloqueio (inclui internos) de forma resiliente."""
        d = _digits_only(tel)
        if not d:
            return False
        try:
            # usa os helpers globais, se existirem
            if 'is_internal_number' in globals() and is_internal_number(d):
                return True
            if 'is_blocked_number' in globals() and is_blocked_number(d):
                return True
        except Exception as e:
            logging.exception("Falha em is_blocked/internal_number: %r", e)

        # fallback seguro
        try:
            return d in BLOCKED_NUMBERS
        except Exception as e:
            logging.exception("Fallback BLOCKED_NUMBERS falhou: %r", e)
            return False

    def _get_warm_minutes() -> int:
        try:
            return int(CONTEXT_WARM_MIN)
        except Exception:
            return int(os.getenv("CONTEXT_WARM_MIN", "3"))

    def _get_lookback_msgs() -> int:
        try:
            return int(CONTEXT_LOOKBACK_MSGS)
        except Exception:
            return int(os.getenv("CONTEXT_LOOKBACK_MSGS", "15"))

    # Histórico curto (fallback quando _fetch_recent_texts_for_chat não existir)
    def _fetch_recent_history_for_dm(telefone: str, limit: int) -> List[dict]:
        try:
            q = (supabase.table("mensagens")
                 .select("fromMe, mensagem, created_at")
                 .eq("telefone", telefone)
                 .is_("group_id", None)
                 # Excluir mensagens que vieram do próprio bot
                 .neq("fromMe", True)
                 .order("created_at", desc=True)
                 .limit(limit))
            data = (q.execute().data) or []
            msgs = []
            for r in reversed(data):
                # garantir que cada item é um dict antes de chamar .get (ajuda o verificador estático)
                if not isinstance(r, dict):
                    continue
                m = r.get("mensagem") or {}
                txt_h = (m.get("text") or "").strip()
                if not txt_h:
                    continue
                role = "assistant" if bool(r.get("fromMe")) else "user"
                if txt_h.lower() in {"ok","obg","obrigado","👍","valeu","show"}:
                    continue
                msgs.append({"role": role, "content": txt_h})
            return msgs
        except Exception:
            return []

    # ---------------- fluxo ----------------
    row_id = None
    try:
        _load_prompts()
        row_id = row.get(ID_COLUMN)
        telefone = (row.get("telefone") or row.get("from") or "").strip()

        mensagem_dict = row.get("mensagem")
        if not isinstance(mensagem_dict, dict):
            mensagem_dict = {}
            row["mensagem"] = mensagem_dict
        meta = mensagem_dict.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            mensagem_dict["meta"] = meta
        in_group = bool(meta.get("is_group")) or bool(row.get("group_id"))
        group_name = row.get("group_name") or row.get("Group_name") or meta.get("group_name")

        # Ignora grupos
        if in_group:
            return

        # Bloqueio por número
        if _safe_is_blocked_number(telefone):
            # MANTER registro no Supabase (histórico) mas evitar qualquer processamento de IA.
            # Não alteramos o campo `status` para não esconder a mensagem no painel; apenas
            # garantimos que não será usada IA e limpamos rascunhos.
            _supabase_update_safe(row_id, {
                "used_ai": False,
                "ai_draft": None,
                "error": "Número em lista de bloqueio"
            })
            return

        debounced_messages: List[dict] = []
        batch_count = meta.get("debounce_batch_count")
        if isinstance(batch_count, int) and batch_count > 1:
            debounced_messages = row.get("_debounced_messages") or _fetch_debounced_messages(row)
            row["_debounced_messages"] = debounced_messages
            unified_text = meta.get("debounce_unified_text") or montar_texto_debounced_para_ia(debounced_messages)
            if unified_text:
                meta["debounce_unified_text"] = unified_text
                mensagem_dict["text"] = unified_text

            batch_ids = meta.get("debounce_batch_ids")
            if not batch_ids:
                batch_ids = [rid for rid in (_safe_row_id(m) for m in debounced_messages) if rid is not None]
                if batch_ids:
                    meta["debounce_batch_ids"] = batch_ids
            if meta.get("debounce_batch_before_id") is None and batch_ids:
                meta["debounce_batch_before_id"] = min(batch_ids)

        # Texto + enrich de mídia
        txt = mensagem_dict.get("text") or ""
        try:
            enriched = enrich_row_with_media_text(row)
            if enriched.get("changed"):
                row = enriched["row"]
                if _column_exists("mensagem"):
                    _supabase_update_safe(row_id, {"mensagem": row.get("mensagem")})
                mensagem_dict = row.get("mensagem")
                if not isinstance(mensagem_dict, dict):
                    mensagem_dict = {}
                    row["mensagem"] = mensagem_dict
                meta = mensagem_dict.get("meta") or meta
                if not isinstance(meta, dict):
                    meta = {}
                    mensagem_dict["meta"] = meta
                txt = (mensagem_dict.get("text") or txt)
        except Exception as _e_media:
            print(">> aviso: enrich_row_with_media_text falhou:", _e_media, flush=True)

        if not (txt or "").strip():
            _supabase_update_safe(row_id, {
                "status": "ignored_empty_text",
                "ai_draft": "Mensagem sem texto (pode ser mídia ou somente metadados).",
                "used_ai": False
            })
            _teams_notify_log(row, title="🗂️ Mensagem sem texto — log", status_tag="ignored_empty_text")
            return

        if is_finalizing_message(txt):
            _supabase_update_safe(row_id, {
                "ai_draft": None, "used_ai": False,
                "status": "ignored_finalizer",
                "error": "Mensagem de encerramento (ok/fechou)."
            })
            _teams_notify_log(row, title="🧹 Finalizador detectado — log", status_tag="ignored_finalizer")
            return

        # Smalltalk (saudação/ack/reciprocidade)
        try:
            smalltalk = (_safe_is_greeting(txt) or is_ack(txt) or is_reciprocidade(txt)) and (not is_finalizing_message(txt))
        except Exception:
            smalltalk = False
        smalltalk_hint = (
            "A mensagem é de cortesia/saudação/agradecimento (smalltalk). "
            "Responda de forma natural e simpática, sem prometer 'verificar' nada a menos que exista pedido técnico claro."
        )
        # Exemplos para guiar o tom/estilo (few-shot). O prefixo 'Julia.' é um identificador
        # interno e será mantido pelo sistema; portanto as respostas devem ser curtas, calorosas
        # e diretamente direcionadas ao cliente.
        smalltalk_examples = (
            "Exemplos de saudações e respostas curtas:\n"
            "Usuário: Oi, tudo bem?\nAssistente: Julia. Oi! Tudo ótimo, e você?\n\n"
            "Usuário: Obrigado!\nAssistente: Julia. Por nada — quando precisar, estou por aqui.\n\n"
            "Usuário: Boa tarde\nAssistente: Julia. Boa tarde! Como posso ajudar hoje?"
        )
        smalltalk_hint = smalltalk_hint + "\n\n" + smalltalk_examples

        # Portão de contexto
        now_ts = _now_ts()
        warm_minutes = _get_warm_minutes()
        globals().setdefault("_last_greeting_at", {})
        if _safe_is_greeting(txt):
            _last_greeting_at[telefone] = now_ts

        last_greet = _last_greeting_at.get(telefone, 0)
        warm_window = (now_ts - last_greet) <= (warm_minutes * 60) if last_greet else False

        if _safe_is_followup(txt) and warm_window:
            context_mode = "RECENT"
        elif _safe_is_logistica(txt):
            context_mode = "RECENT"
        else:
            context_mode = "LAST_ONLY"

        # Clarify
        clarify = _needs_clarify(txt)
        needs_clarify = bool(clarify and clarify != "__ignore_greeting__")
        clarify_hint = clarify if needs_clarify else None

        # Horário comercial
        OOH_STRATEGY = (os.getenv("OOH_STRATEGY", "reply") or "reply").lower()
        try:
            is_open = bool(_within_business_hours())
        except Exception:
            is_open = True

        if not is_open:
            if OOH_STRATEGY == "queue":
                _supabase_update_safe(row_id, {"status": "queued_business_hours", "used_ai": False, "ai_draft": None})
                _teams_notify_log(row, title="🌙 Fora do expediente — fila", status_tag="queued_business_hours")
                return
            elif OOH_STRATEGY == "draft":
                _supabase_update_safe(row_id, {"status": "draft_ooh", "used_ai": True})
                _teams_notify_log(row, title="🌙 Fora do expediente — rascunho", status_tag="draft_ooh")
            else:
                _teams_notify_log(row, title="🌙 Fora do expediente — resposta automática autorizada", status_tag="ooh_reply")

        # Roteamento interno
        route = _classify_route(txt)
        if route in {"admin", "log"}:
            _notify_internal(route, txt, telefone_cli=telefone, group_name=group_name)

        # Histórico (chat memory) — só quando RECENT
        history_block = None
        history_lines = []
        if context_mode == "RECENT":
            try:
                history_lines = _fetch_recent_texts_for_chat(
                    telefone=telefone, group_id=None,
                    limit=CTX_HISTORY_LIMIT, before_id=row_id, window_hours=24
                )
            except Exception:
                history_struct = _fetch_recent_history_for_dm(telefone, limit=_get_lookback_msgs())
                for h in history_struct:
                    role = h.get("role") or "user"
                    content = (h.get("content") or "").strip()
                    if content:
                        history_lines.append(f"{role}: {content}")
            history_block = "\n".join(history_lines) if history_lines else None

        APP_LOG.info("historico DM | tel=%s | mode=%s | fetched=%d | limit=%d | before_id=%s",
                     telefone, context_mode, len(history_lines or []), CTX_HISTORY_LIMIT, row_id)

        # Geração da resposta via ChatGPT centralizado
        chat_key = f"phone:{telefone}" if telefone else f"anon:{row_id}"
        user_identifier = telefone or chat_key

        try:
            if '_RUN_LOCKS' not in globals():
                from collections import defaultdict
                globals()['_RUN_LOCKS'] = defaultdict(threading.Lock)

            lock = _RUN_LOCKS[chat_key]
            with lock:
                resposta = gerar_resposta_com_chatgpt(txt, user_identifier)
        except Exception as exc:
            print(">> erro: gerar_resposta_com_chatgpt falhou:", exc, flush=True)
            _supabase_update_safe(row_id, {
                "status": "error",
                "used_ai": False,
                "ai_draft": None,
                "error": f"ChatGPT falhou: {exc}"
            })
            _teams_notify_log(row, title="⚠️ Falha ao gerar resposta — log", status_tag="ai_error")
            return

        if not resposta or not resposta.strip():
            _supabase_update_safe(row_id, {
                "status": "ignored_empty_ai",
                "used_ai": False,
                "ai_draft": None,
                "error": "ChatGPT retornou vazio"
            })
            _teams_notify_log(row, title="🧹 Resposta vazia — log", status_tag="ignored_empty_ai")
            return

        analysis_obj = {
            "chat_key": chat_key,
            "route": route,
            "context_mode": context_mode,
            "generator": "chatgpt",
            "history_source": "conversas",
            "used_tools": False,
        }

        # Saída
        if APPROVAL_MODE:
            # tenta extrair JSON com as duas saídas que pedimos ao modelo
            try:
                rc, ms = _extract_json_outputs_from_text(resposta or "")
            except Exception:
                rc, ms = (None, None)

            # se o modelo retornou resposta_cliente, usamos ela como ai_draft
            ai_for_client = rc.strip() if isinstance(rc, str) and rc.strip() else resposta

            _supabase_update_safe(row_id, {
                "ai_draft": ai_for_client,
                "status": "awaiting_approval",
                "used_ai": True,
                "error": None,
                "analysis": analysis_obj,
            })

            # Sempre enviar o card de aprovação para o canal principal (projetos)
            try:
                _teams_notify(row, ai_for_client, route, channel="projetos")
            except Exception as e:
                print(">> [WARN] falha ao enviar card de aprovação ao canal projetos:", e, flush=True)

            # Enviar mensagem adicional para o setor específico (admin/estoque), se aplicável
            try:
                setor = decidir_canal_teams_from_row(row, history_lines)
            except Exception:
                setor = "projetos"

            if setor in ("admin", "estoque"):
                # se IA já forneceu mensagem_setor (ms), usa-a; senão monta uma mensagem detalhada
                if isinstance(ms, str) and ms.strip():
                    titulo_setor = "Mensagem interna — Lucenera"
                    texto_setor = ms.strip()
                else:
                    titulo_setor, texto_setor = _montar_mensagem_setor_detalhada(
                        row,
                        ai_for_client,
                        setor,
                        history_lines=history_lines,
                    )

                try:
                    _teams_post_card(title=titulo_setor, text=texto_setor, buttons=None, color="0078D7", channel=setor)
                except Exception as e:
                    print(">> [WARN] falha ao enviar mensagem_setor ao Teams:", e, flush=True)
        else:
            sent_ok = False
            if OUTGOING_ENABLED:
                try:
                    sent_ok = bool(send_text_from_row(row, resposta))
                except Exception as e_send:
                    print(">> aviso: falha ao enviar WhatsApp:", e_send, flush=True)

            # antes de enviar para o cliente, tentar extrair JSON com resposta_cliente/mensagem_setor
            try:
                rc, ms = _extract_json_outputs_from_text(resposta or "")
            except Exception:
                rc, ms = (None, None)

            to_send = rc.strip() if isinstance(rc, str) and rc.strip() else resposta

            if sent_ok:
                _supabase_update_safe(row_id, {
                    "final_out": to_send,
                    "status": "sent",
                    "used_ai": True,
                    "approved": True,
                    "error": None,
                    "analysis": analysis_obj,
                })
                _teams_notify_log(row, title="📤 Enviado (auto) — log", status_tag="sent")
                # se havia mensagem_setor, enviar ao setor específico (admin/estoque)
                if isinstance(ms, str) and ms.strip():
                    try:
                        setor = decidir_canal_teams_from_row(row, history_lines)
                    except Exception:
                        setor = "projetos"
                    if setor in ("admin", "estoque"):
                        try:
                            _teams_post_card(title="Mensagem interna — Lucenera", text=ms.strip(), buttons=None, color="0078D7", channel=setor)
                        except Exception as e:
                            print(">> [WARN] falha ao enviar mensagem_setor ao Teams:", e, flush=True)
                try:
                    supabase.table("mensagens").insert({
                        "telefone": telefone,
                        "group_id": None,
                        "mensagem": {"text": resposta, "meta": {"type": "outgoing", "status": "SENT"}},
                        "fromMe": True, "from_me": True, "direction": "out", "status": "SENT", "origem": "bot"
                    }).execute()
                except Exception as e:
                    print(">> aviso: falha ao registrar fala do bot:", e, flush=True)
            else:
                _supabase_update_safe(row_id, {
                    "ai_draft": resposta,
                    "status": ("sent_dry_run" if not OUTGOING_ENABLED else "error"),
                    "used_ai": True,
                    "approved": False,
                    "error": (None if not OUTGOING_ENABLED else "Falha no envio WhatsApp"),
                    "analysis": analysis_obj,
                })
                _teams_notify_log(
                    row,
                    title=("🧪 DRY RUN (auto) — log" if not OUTGOING_ENABLED else "⚠️ Erro de envio — log"),
                    status_tag=("sent_dry_run" if not OUTGOING_ENABLED else "error")
                )

    except Exception as e:
        print(">> processar_inline erro:", e, flush=True)
        if row_id is not None:
            _supabase_update_safe(row_id, {
                "ai_draft": None, "used_ai": False, "status": "error",
                "error": f"processar_inline: {type(e).__name__}: {e}"
            })
        _teams_notify_log(row, title="💥 Exceção no processamento — log", status_tag="error", note=str(e))



# =====================================================================
# ROTAS HTTP
# =====================================================================
@app.post("/upload_imagem")
def upload_imagem():
    if "imagem" not in request.files: return "Nenhum arquivo foi enviado", 400
    imagem_enviada = request.files["imagem"]
    nome_arquivo = f"{uuid.uuid4()}{os.path.splitext(imagem_enviada.filename)[1]}"
    caminho_arquivo = os.path.join(UPLOAD_FOLDER, nome_arquivo)
    imagem_enviada.save(caminho_arquivo)
    return "Imagem recebida com sucesso!", 200

@app.post("/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    prompt = (payload.get("msg") or "").strip()
    origem = payload.get("origem") or "web"
    telefone = payload.get("telefone")
    nome = payload.get("nome")
    if not prompt: return Response("Campo 'msg' obrigatório.", status=400)

    if supabase:
        row_in = {"telefone": telefone,"mensagem": {"text": prompt, "meta":{"origem": origem}},"nome": {"display": nome} if nome else None,"data": _now_iso(),"ai_draft": None,"used_ai": False,"approval_mode": APPROVAL_MODE,"status": "received"}
        out = supabase.table(TABLE).insert(row_in).execute()
        data = out.data or []
        if data: processar_inline(data[0])
    return jsonify({"reply": "Sua mensagem foi recebida. Processando..."})

def _is_message_event(ev: dict) -> bool:
    if not isinstance(ev, dict): return False
    event_type = str(ev.get("type") or ev.get("event") or "").strip().lower()
    if event_type == "deliverycallback":
        return True
    if ev.get("fromMe") is True: return True
    if _extract_text_from_payload(ev): return True
    if any(k in ev for k in ("image","video","audio","document")): return True
    return False

@app.route("/webhook", methods=["GET", "POST"])
@app.route("/webhook/whatsapp", methods=["GET", "POST"])
def webhook_whatsapp(): 
    if request.method == "GET":
        return {"ok": True, "message": "Webhook ativo. Use POST para eventos do Z-API/WhatsApp."}, 200

    print(">> /webhook* METHOD:", request.method)
    try:
        print(">> /webhook* HEADERS:", dict(request.headers))
    except Exception:
        pass

    data = request.get_json(silent=True) or {}
    form_dict, files_dict = {}, {}
    if not data:
        try:
            form_dict = request.form.to_dict(flat=True) or {}
        except Exception:
            form_dict = {}
        try:
            files_dict = {k: v.filename for k, v in (request.files or {}).items()}
        except Exception:
            files_dict = {}

    raw = request.get_data(cache=False, as_text=True) or ""
    try:
        safe_raw = raw[:2000]
        # Prepare a console-safe version: replace characters that can't be
        # encoded by the console's encoding (common Windows cp1252 issue).
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        display_raw = safe_raw.encode(enc, "replace").decode(enc, "replace")
    except Exception:
        display_raw = "<raw unavailable>"
    print(
        ">> /webhook* RAW (primeiros 2000):",
        display_raw,
        flush=True,
    )
    try:
        import os as _os
        print(f">> telemetry: pid={_os.getpid()} argv0={_os.path.basename(sys.argv[0])} supabase_present={bool(supabase)} supabase_type={type(supabase).__name__ if supabase is not None else 'None'}", flush=True)
    except Exception:
        pass
    if form_dict: print(">> /webhook* FORM:", form_dict)
    if files_dict: print(">> /webhook* FILES:", files_dict)

    payload = data if data else form_dict
    events: List[dict] = []
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        events = [payload["data"]]
    elif isinstance(payload, dict):
        events = [payload]
    else:
        events = []

    saved_any = False
    for ev in events:
        if not _is_message_event(ev):
            continue
        # Early normalize to permitir identificação rápida
        try:
            norm_ev = parse_zapi_payload(ev or {})
        except Exception:
            norm_ev = {}

        event_type_norm = str(norm_ev.get("type") or ev.get("type") or ev.get("event") or "").strip().lower()
        if event_type_norm == "deliverycallback":
            saved_cb = _save_delivery_callback(ev, parsed=norm_ev)
            status_log = next(
                (
                    str(candidate).strip()
                    for candidate in (
                        norm_ev.get("status"),
                        ev.get("status"),
                        ev.get("deliveryStatus"),
                        ev.get("error"),
                    )
                    if isinstance(candidate, str) and candidate.strip()
                ),
                "",
            )
            message_id_log = (norm_ev.get("message_id") or ev.get("messageId") or "").strip()
            telefone_log = _digits_only(norm_ev.get("telefone") or ev.get("phone") or "")
            print(
                f">> DELIVERY_CALLBACK_ACCEPTED message_id={message_id_log or '-'} status={status_log or '-'} phone={telefone_log or '-'} saved={bool(saved_cb)}",
                flush=True,
            )
            continue

        try:
            if is_internal_message(norm_ev):
                saved_row = _save_in_supabase_from_zapi(ev, parsed=norm_ev, internal_only=True)
                if saved_row:
                    saved_any = True
                continue
        except Exception as _e_internal:
            print(">> aviso: falha ao processar mensagem interna:", _e_internal, flush=True)

        telefone_chk_early = (norm_ev.get("telefone") or "")

        try:
            if telefone_chk_early and is_blocked_number(telefone_chk_early):
                print(f">> [BLOCKED] Ignorando completamente mensagem de número bloqueado: {telefone_chk_early}", flush=True)
                return jsonify({"ok": True, "blocked": True, "saved": False, "processed": False}), 200
        except Exception:
            pass

        row = _save_in_supabase_from_zapi(ev, parsed=norm_ev)
        if not row:
            continue
        saved_any = True

        print(
            "[DEBUG WEBHOOK] novo evento salvo.",
            "telefone row:", row.get("telefone"),
            "OUTGOING_ENABLED:", OUTGOING_ENABLED,
            flush=True,
        )

        telefone_norm_row = _digits_only(row.get("telefone") or "")
        if telefone_norm_row and telefone_norm_row in ENTREGADORES_WHATS:
            reply_text = handle_delivery_event(
                row,
                telefone_norm_row,
                raw_event=ev,
                supabase_client=supabase,
                teams_notify_func=_notify_delivery_teams,
            )
            print(
                "DELIVERY_WIZARD_BYPASS_DEBOUNCE phone=",
                telefone_norm_row,
                "reply_present=",
                bool(reply_text),
                flush=True,
            )
            row["__entrega_flow__"] = True
            row["__delivery_flow__"] = True
            if reply_text:
                telefone_destino = row.get("telefone")
                if telefone_destino and OUTGOING_ENABLED:
                    try:
                        send_text_to(phone=telefone_destino, message=reply_text)
                    except Exception as envio_exc:
                        print(
                            f">> deliveries_flow: erro ao enviar resposta automatica: {envio_exc}",
                            flush=True,
                        )
                else:
                    print(
                        ">> [DRY RUN] deliveries_flow: resposta nao enviada (OUTGOING_ENABLED=0 ou telefone ausente)",
                        flush=True,
                    )
            return jsonify({"ok": True, "entrega_flow": True, "delivery_flow": True, "reply_sent": bool(reply_text)}), 200


        # skip grupos
        try:
            meta = (row.get("mensagem") or {}).get("meta") or {}
            is_group = bool(row.get("group_id")) or bool(meta.get("is_group"))
        except Exception:
            is_group = False
        # detectar de forma robusta se a mensagem foi enviada pelo time/empresa
        try:
            is_from_me = _row_is_from_me(row)
        except Exception:
            is_from_me = False

        # >>> Se a mensagem veio "de mim" (time interno), já está salva para histórico.
        # Não entra no pipeline/AI/debounce.
        if is_from_me:
            try:
                rid = row.get(ID_COLUMN)
                _supabase_update_safe(rid, {"status": row.get("status") or "sent"})
            except Exception:
                pass
            continue

        if is_group:
            try:
                rid = row.get(ID_COLUMN)
                _supabase_update_safe(rid, {
                    "status": "ignored_group_disabled",
                    "ai_draft": None,
                    "used_ai": False,
                    "error": "Processamento de grupos desativado (apenas conversa direta)."
                })
            except Exception as _e:
                print(">> aviso: falha ao marcar grupo como ignorado:", _e, flush=True)
            continue

        if not is_from_me:
            chat_key = _row_chat_key(row)
            _schedule_debounce(chat_key, row)

    return {"ok": True, "saved": saved_any}, 200


# ---- AÇÕES VIA TEAMS
def _cast_key_for_query(val: str):
    if ID_COLUMN.lower() in {"id","id_num","idnum","numero","pk","num"}:
        try: return int(val)
        except Exception: return val
    return val

@app.get("/teams/approve")
def teams_approve():
    # Debug: log args and token comparison to help diagnose missing approvals
    try:
        incoming_args = dict(request.args)
    except Exception:
        incoming_args = {}
    incoming_token = (request.args.get("token") or "")
    print(f">> /teams/approve called args={incoming_args}", flush=True)
    if incoming_token != (TEAMS_ACTION_TOKEN or ""):
        print(f">> /teams/approve: token mismatch incoming={incoming_token!r} expected={(TEAMS_ACTION_TOKEN or '')!r}", flush=True)
        return "forbidden", 403
    rid = request.args.get("id")
    if not rid:
        return "id obrigatório", 400
    if not supabase:
        return "supabase indisponível", 500
    try:
        row = supabase.table(TABLE).select("*").eq(ID_COLUMN, _cast_key_for_query(rid)).single().execute().data
    except Exception as e:
        return f"erro ao buscar: {e}", 500
    if not row:
        return "não encontrado", 404
    texto = (row.get("ai_draft") or "").strip()
    if not texto:
        return "sem conteúdo para enviar (ai_draft vazio)", 400
    ok = False
    if OUTGOING_ENABLED:
        print(f">> /teams/approve: OUTGOING_ENABLED=1 - attempting send. row_id={rid}", flush=True)
        try:
            print(f">> /teams/approve: row telefone={row.get('telefone')}, group_id={row.get('group_id')}", flush=True)
        except Exception:
            pass
        ok = send_text_from_row(row, texto)
    else:
        print("[DRY RUN] OUTGOING_ENABLED=0 — não enviando WhatsApp.")
    _supabase_update_safe(_cast_key_for_query(rid), {"final_out": texto if ok or not OUTGOING_ENABLED else None,"approved": True,"status": "sent" if ok else ("sent_dry_run" if not OUTGOING_ENABLED else "error"),"error": None if ok or not OUTGOING_ENABLED else "Falha no envio WhatsApp"})
    if ok:
        try:
            supabase.table("mensagens").insert({
                "telefone": row.get("telefone"),
                "group_id": row.get("group_id"),
                "mensagem": {"text": texto, "meta": {"type": "outgoing", "status": "SENT"}},
                "fromMe": True, "from_me": True, "direction": "out",
                "status": "SENT",
                "origem": "bot"
            }).execute()
        except Exception as e:
            print(">> aviso: falha ao registrar fala do bot (approve):", e, flush=True)
    return redirect(url_for("admin"))

@app.get("/teams/reject")
def teams_reject():
    if (request.args.get("token") or "") != (TEAMS_ACTION_TOKEN or ""):
        return "forbidden", 403
    rid = request.args.get("id")
    if not rid:
        return "id obrigatório", 400
    if not supabase:
        return "supabase indisponível", 500
    _supabase_update_safe(_cast_key_for_query(rid), {"approved": False, "status": "rejected"})
    return redirect(url_for("admin"))
# =========================
# TEAMS - Sugerir resposta manual
# =========================
@app.get("/teams/suggest")
def teams_suggest():
    from flask import render_template_string, request
    msg_id = request.args.get("id")
    token = request.args.get("token")
    # Debug: log incoming args for diagnosis
    try:
        incoming_args = dict(request.args)
    except Exception:
        incoming_args = {}
    print(f">> /teams/suggest (GET) called args={incoming_args}", flush=True)
    if token != (TEAMS_ACTION_TOKEN or ""):
        print(f">> /teams/suggest (GET): token mismatch incoming={token!r} expected={(TEAMS_ACTION_TOKEN or '')!r}", flush=True)
        return "Token inválido", 403

    # Página simples de sugestão
    html = f"""
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Sugerir resposta - Lucenera</title>
        <style>
            body {{
                font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
                margin: 40px;
                color: #333;
            }}
            textarea {{
                width: 100%;
                height: 140px;
                font-size: 15px;
                padding: 8px;
                border-radius: 6px;
                border: 1px solid #ccc;
                resize: vertical;
            }}
            button {{
                background: #2563eb;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                margin-top: 10px;
            }}
            button:hover {{ background: #1d4ed8; }}
        </style>
    </head>
    <body>
        <h2>💬 Sugerir resposta manual</h2>
        <form method="post" action="/teams/suggest">
            <input type="hidden" name="id" value="{msg_id}">
            <input type="hidden" name="token" value="{token}">
            <textarea name="texto" placeholder="Escreva aqui a resposta sugerida..."></textarea><br>
            <button type="submit">Enviar sugestão</button>
        </form>
    </body>
    </html>
    """
    return render_template_string(html)


@app.post("/teams/suggest")
def teams_suggest_submit():
    from flask import request
    msg_id = request.form.get("id")
    token = request.form.get("token")
    texto = request.form.get("texto") or ""
    # Debug: log form args and token status for diagnosis
    try:
        form_args = dict(request.form)
    except Exception:
        form_args = {}
    print(f">> /teams/suggest (POST) called form={form_args}", flush=True)
    if token != (TEAMS_ACTION_TOKEN or ""):
        print(f">> /teams/suggest (POST): token mismatch incoming={token!r} expected={(TEAMS_ACTION_TOKEN or '')!r}", flush=True)
        return "Token inválido", 403
    if not texto.strip():
        return "Mensagem vazia", 400

    rid = _cast_key_for_query(msg_id)

    # Marca sugestão no Supabase primeiro
    _supabase_update_safe(rid, {
        "manual_reply": texto,
        "status": "suggested",
        "approved": False,
        "approved_by": "Teams",
        "origem": "human"
    })

    # Tenta buscar a linha para enviar (se OUTGOING_ENABLED)
    row = None
    try:
        if supabase:
            row = supabase.table(TABLE).select("*").eq(ID_COLUMN, rid).single().execute().data
    except Exception as e:
        print(f">> aviso: falha ao buscar row para envio (suggest): {e}", flush=True)

    _record_human_suggestion(
        telefone=(row or {}).get("telefone") if row else None,
        texto=texto,
        group_id=(row or {}).get("group_id") if row else None,
        client_row=row,
        source="teams",
        author="Teams",
        reply_to=rid,
    )

    _supabase_update_safe(rid, {
        "final_out": None,
        "manual_reply": texto,
        "approved": False,
        "approved_by": "Teams",
        "status": "suggested",
        "origem": "human_suggestion",
        "used_ai": False,
        "error": None,
    })

    print(f">> Sugestão registrada via Teams (id={rid}) sent=False")
    return "<h3>✅ Sugestão registrada com sucesso!</h3><p>Você pode fechar esta janela.</p>"

@app.get("/favicon.ico")
def favicon(): return "", 204

@app.get("/")
def home(): return render_template("index.html")

@app.get("/ping")
def ping():
    return "pong"

# =====================================================================
# /admin
# =====================================================================
@app.get("/admin")
def admin():
    if not supabase:
        return "Supabase não configurado.", 500
    f_status = request.args.get("status") or ""
    q = (request.args.get("q") or "").strip()
    order_param = (request.args.get("order") or ID_COLUMN).lower()
    limit = _to_int(request.args.get("limit"), 100) or 100
    before = request.args.get("before")
    refresh = _to_int(request.args.get("refresh"), 0) or 0
    try_cols = [ID_COLUMN]
    for c in ("telefone", "id_num", "data", "id", "ID"):
        if c not in try_cols:
            try_cols.append(c)
    rows: List[Dict[str, Any]] = []
    used_col = None
    for col in try_cols:
        if not _column_exists(col):
            continue
        try:
            qb = supabase.table(TABLE).select("*").order(col, desc=True)
            if before and col in ("telefone", "id_num"):
                before_cast = _cast_key_for_query(before) if col == ID_COLUMN else before
                qb = qb.lt(col, before_cast)
            if f_status:
                qb = qb.eq("status", f_status)
            rows = qb.limit(limit).execute().data or []
            used_col = col
            break
        except Exception as e:
            print(f">> /admin: falhou ordenar por '{col}', tentando próximo. Erro:", e, flush=True)
            continue
    if used_col is None:
        try:
            qb = supabase.table(TABLE).select("*")
            if f_status:
                qb = qb.eq("status", f_status)
            rows = qb.limit(limit).execute().data or []
            print(">> /admin: usando fallback sem ordenação.", flush=True)
        except Exception as e:
            print(">> /admin: fallback sem ordenação também falhou:", e, flush=True)
            rows = []
    for r in rows:
        nm = r.get("nome")
        if isinstance(nm, str) or nm is None:
            r["nome"] = {"display": nm or ""}
        msg = r.get("mensagem")
        if isinstance(msg, str) or msg is None:
            r["mensagem"] = {"text": msg or ""}
        if r.get("is_group") is None:
            _meta = (r.get("mensagem") or {}).get("meta") or {}
            r["is_group"] = bool(_meta.get("is_group")) or bool(r.get("group_id") or "")
        meta = (r.get("mensagem") or {}).get("meta") or {}
        group_name = (r.get("group_name") or r.get("Group_name") or meta.get("group_name") or "").strip() or "(sem nome)"
        r["grupo"] = f"grupo — {group_name}" if r.get("is_group") else "pessoa"
        r["group_name_display"] = group_name
    if q:
        q_lower = q.lower()
        def _match(r):
            tel = (r.get("telefone") or "").lower()
            nome = (r.get("nome") or {}).get("display", "").lower()
            txt = (r.get("mensagem") or {}).get("text", "").lower()
            return (q_lower in tel) or (q_lower in nome) or (q_lower in txt)
        rows = [r for r in rows if _match(r)]
    next_before = rows[-1].get(ID_COLUMN) if rows else None
    return render_template("admin.html",
        rows=rows, f_status=f_status, q=q, id_col=ID_COLUMN,
        order_by=used_col or order_param, limit=limit, before=before,
        next_before=next_before, refresh=refresh)

@app.get("/admin/json")
def admin_json():
    if not supabase: return {"error": "Supabase não configurado"}, 500
    try:
        rows = (supabase.table(TABLE).select("*").order(ID_COLUMN, desc=True).limit(50).execute().data or []
        )
        return {"ok": True, "count": len(rows), "items": rows}
    except Exception as e:
        return {"ok": False, "error": str(e)}, 500

@app.post("/admin/action")
def admin_action():
    if not supabase:
        return "Supabase não configurado.", 500

    form = request.form
    row_id = form.get("row_id")
    op = form.get("op")
    telefone = form.get("telefone") or ""
    group_id = form.get("group_id") or ""
    texto = form.get("texto") or ""
    row_id_cast = _cast_key_for_query(row_id)

    # === AÇÃO: Aprovar e Enviar (fluxo padrão)
    if op == "aprovar":
        ok = False
        if OUTGOING_ENABLED:
            if telefone:
                ok = send_text_to(phone=telefone, message=texto)
            else:
                ok = False
        else:
            print("[DRY RUN] Envio WhatsApp bloqueado (OUTGOING_ENABLED=0).")

        _supabase_update_safe(row_id_cast, {
            "final_out": texto if ok or not OUTGOING_ENABLED else None,
            "approved": True,
            "status": "sent" if ok else ("sent_dry_run" if not OUTGOING_ENABLED else "error"),
            "error": None if ok or not OUTGOING_ENABLED else "Falha no envio WhatsApp"
        })

        if ok:
            try:
                supabase.table("mensagens").insert({
                    "telefone": telefone or None,
                    "group_id": group_id or None,
                    "mensagem": {"text": texto, "meta": {"type": "outgoing", "status": "SENT"}},
                    "fromMe": True, "from_me": True, "direction": "out",
                    "status": "SENT",
                    "origem": "bot"
                }).execute()
            except Exception as e:
                print(">> aviso: falha ao registrar fala do bot (admin_action):", e, flush=True)

    # === AÇÃO: Rejeitar
    elif op == "rejeitar":
        _supabase_update_safe(row_id_cast, {
            "approved": False,
            "status": "rejected"
        })

    # === AÇÃO: Enviar Resposta Manual (novo fluxo)
    elif op == "enviar":
        texto = form.get("texto") or ""
        if not texto.strip():
            return "Mensagem vazia", 400

        client_row = None
        if supabase:
            try:
                client_row = (
                    supabase.table(TABLE)
                    .select("*")
                    .eq(ID_COLUMN, row_id_cast)
                    .single()
                    .execute()
                    .data
                )
            except Exception as e:
                print(">> aviso: falha ao obter row antes de registrar sugestão (admin):", e, flush=True)

        _record_human_suggestion(
            telefone=telefone,
            texto=texto,
            group_id=group_id or None,
            client_row=client_row,
            source="admin",
            author="Painel Admin",
            reply_to=row_id_cast,
        )

        _supabase_update_safe(row_id_cast, {
            "manual_reply": texto,
            "approved": False,
            "approved_by": "Painel Admin",
            "status": "suggested",
            "used_ai": False,
            "final_out": None,
            "error": None,
        })

        return redirect(url_for("admin"))



# =====================================================================
# SILENCIAR LOGS DO /ping
# =====================================================================
@app.before_request
def suprimir_logs_ping():
    if request.path == '/ping': log.disabled = True
    else: log.disabled = False

# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    port = int(os.getenv("PORT", str(PORT)))

    if NGROK_KILL_ON_START:
        print(">> NGROK_KILL_ON_START=1 — finalizando ngrok(s) antigos...", flush=True)
        kill_ngrok_processes()

    # Allow disabling ngrok autostart for local testing via DISABLE_NGROK env var
    try:
        if str(os.getenv("DISABLE_NGROK") or "").strip().lower() in {"1", "true", "yes"}:
            NGROK_AUTOSTART = False
    except Exception:
        pass

    if NGROK_AUTOSTART:
        try:
            if NGROK_AUTHTOKEN:
                subprocess.run([NGROK_BIN, "config", "add-authtoken", NGROK_AUTHTOKEN], check=False)
            subprocess.Popen([NGROK_BIN, "http", str(port), "--region", NGROK_REGION, "--log", "stdout"], cwd=str(BASE_DIR))
        except Exception as e:
            print(">> ngrok: não inicializado:", e, flush=True)

    # Valida persistência de public base (remove se estiver desatualizada)
    try:
        _validate_persisted_public_base()
    except Exception:
        pass

    public_base = PUBLIC_BASE_URL or _get_ngrok_public_url()
    if public_base:
        print(f">> URL pública detectada: {public_base}", flush=True)
    # Mostra qual URL efetiva será usada em links de Teams/cards
    try:
        effective = _effective_base_url()
        print(f">> URL efetiva usada em links (PUBLIC_BASE_URL/ngrok/localhost): {effective}", flush=True)
        if str(effective).startswith("http://127.0.0.1"):
            print(
                ">> AVISO: URL efetiva é localhost. Pessoas fora desta máquina não poderão acessar os links. "
                "Inicie ngrok ou defina PUBLIC_BASE_URL para uma URL pública.",
                flush=True
            )
    except Exception:
        pass

    if not supabase:
        print(">> AVISO: Supabase não está configurado/operante. /admin mostrará 'Supabase não configurado.'", flush=True)

    if ZAPI_AUTOCONFIG_WEBHOOKS:
        # Run initial webhook update in background to avoid blocking startup if Z-API is slow/unreachable
        def _init_zapi_update():
            try:
                if public_base:
                    ok = _zapi_update_webhooks(public_base, WEBHOOK_PATH)
                    if ok:
                        _last_webhook["target"] = f"{public_base.rstrip('/')}{WEBHOOK_PATH}"
                        _last_webhook["fail_count"] = 0
                        _last_webhook["next_retry"] = 0
            except Exception as e:
                print(">> Z-API: init update failed:", e, flush=True)

        threading.Thread(target=_init_zapi_update, daemon=True).start()
        threading.Thread(target=_autoupdate_zapi_loop, daemon=True).start()
    else:
        print(">> Z-API: autoconfig desabilitado (ZAPI_AUTOCONFIG_WEBHOOKS=0).", flush=True)

    print("\n=== URLs úteis ===", flush=True)
    print(f"- Admin local:          http://127.0.0.1:{port}/admin", flush=True)
    print(f"- Admin JSON:           http://127.0.0.1:{port}/admin/json", flush=True)
    print(f"- Ping local:           http://127.0.0.1:{port}/ping", flush=True)
    print(f"- ngrok Web UI (local): http://127.0.0.1:4040/inspect/http", flush=True)
    print("======================\n", flush=True)

    print(f">> Iniciando servidor em http://127.0.0.1:{port} (bind 0.0.0.0) ...", flush=True)
    print("[Flask] App iniciado com sucesso.", flush=True)
    app.run(host="0.0.0.0", port=port, use_reloader=False, debug=False)