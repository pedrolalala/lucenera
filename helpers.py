# -*- coding: utf-8 -*-
"""
helpers.py — utilitários genéricos usados pelo app
- IO de arquivos/JSON (com escrita atômica)
- Helpers de imagem (data URL)
- Limpeza/conversões simples
"""

from __future__ import annotations

import os
import json
import base64
import mimetypes
from pathlib import Path
from typing import Any, Optional

# -----------------------------
# Arquivos / JSON
# -----------------------------
def ensure_dir(path: str | os.PathLike) -> None:
    """Garante a existência de um diretório."""
    Path(path).mkdir(parents=True, exist_ok=True)

def ensure_parent(path: str | os.PathLike) -> None:
    """Garante que o diretório pai de um arquivo exista."""
    p = Path(path)
    if p.parent:
        p.parent.mkdir(parents=True, exist_ok=True)

def _strip_bom(text: str) -> str:
    # Remove BOM UTF-8 se houver
    return text.lstrip("\ufeff")

def carrega(caminho: str | os.PathLike, default: Optional[str] = "") -> str:
    """Lê um arquivo texto. Tenta UTF-8, cai para Latin-1. Retorna default se não existir/erro."""
    p = Path(caminho)
    try:
        return _strip_bom(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default or ""
    except Exception:
        try:
            return _strip_bom(p.read_text(encoding="latin-1"))
        except Exception:
            return default or ""

def salvar(caminho: str | os.PathLike, conteudo: str, encoding: str = "utf-8") -> None:
    """Salva arquivo texto com escrita atômica (cria pastas se necessário)."""
    path = Path(caminho)
    ensure_parent(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(conteudo or "", encoding=encoding)
    os.replace(tmp, path)  # atomic replace em sistemas modernos

def ler_json(caminho: str | os.PathLike, default: Any = None) -> Any:
    """Carrega um JSON. Retorna default em caso de erro/arquivo inexistente."""
    txt = carrega(caminho, "")
    if not txt:
        return default
    try:
        return json.loads(txt)
    except Exception:
        return default

def salvar_json(
    caminho: str | os.PathLike,
    data: Any,
    pretty: bool = True,
    sort_keys: bool = False,
) -> None:
    """Salva JSON (atômico) com indentação por padrão."""
    ensure_parent(caminho)
    path = Path(caminho)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if pretty:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=sort_keys),
            encoding="utf-8",
        )
    else:
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=sort_keys),
            encoding="utf-8",
        )
    os.replace(tmp, path)

# -----------------------------
# Imagens
# -----------------------------
def guess_mime(filename: str) -> str:
    """Obtém o MIME type a partir da extensão; fallback genérico."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

def imagem_data_url(path: str | os.PathLike) -> str:
    """
    Converte um arquivo de imagem (PNG/JPG/etc.) para data URL (base64).
    Retorna string vazia em caso de erro.
    """
    p = Path(path)
    try:
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        mime = guess_mime(p.name)
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""

# -----------------------------
# Conversões / limpeza
# -----------------------------
def to_bool(val: Any, default: bool = False) -> bool:
    """Converte valores comuns de texto/numérico para booleano."""
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "sim", "on", "verdadeiro"}:
        return True
    if s in {"0", "false", "f", "no", "n", "nao", "não", "off", "falso"}:
        return False
    return default

def only_digits(s: Optional[str]) -> str:
    """Mantém apenas dígitos de uma string (None -> "")."""
    return "".join(ch for ch in (s or "") if ch.isdigit())

def clean_phone(phone: Optional[str]) -> str:
    """Remove caracteres não numéricos do telefone (não aplica formatação E.164)."""
    return only_digits(phone)

def pretty(obj: Any) -> str:
    """JSON bonitinho para logs (fallback para str(obj))."""
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)

# -----------------------------
# ENV helpers
# -----------------------------
def clean_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """
    Lê uma variável de ambiente, limpando aspas e espaços.
    Retorna default se não definida ou vazia.
    """
    v = os.getenv(name)
    if v is None:
        return default
    v = v.strip().strip('"').strip("'")
    return v or default

# ======================================================
# Extras necessários pro app.py
# ======================================================
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

def _within_business_hours() -> bool:
    """Retorna True se agora for horário comercial (seg–sex, 8h–18h) em America/Sao_Paulo.
    Usa ZoneInfo quando disponível; quando falhar (Windows sem tzdata), usa pytz como fallback.
    Falha deve ser fail-open (considera aberto) para não travar atendimento.
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Sao_Paulo")
        now = datetime.now(tz)
    except Exception as e:
        try:
            import pytz
            tz = pytz.timezone("America/Sao_Paulo")
            now = datetime.now(tz)
        except Exception as e2:
            # Falha total — fail-open para não bloquear
            return True
    if now.weekday() >= 5:  # sábado/domingo
        return False
    start = int(os.getenv("BIZ_START_HOUR", "8"))
    end   = int(os.getenv("BIZ_END_HOUR", "18"))
    return start <= now.hour < end

def _team_is_active(telefone: str, window_minutes: int = 12) -> bool:
    """
    True se teve mensagem 'fromMe' (humano) para esse telefone
    nos últimos N minutos. Evita IA responder junto.
    """
    if not telefone:
        return False
    try:
        from supabase_client import supabase  # lazy import
    except Exception:
        return False

    table = os.getenv("TABLE", "mensagens")
    id_col = os.getenv("ID_COLUMN", "id_num")
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
    try:
        rows = (
            supabase.table(table)
            .select(f"{id_col},fromMe,origem,data")
            .eq("telefone", str(telefone).strip())
            .eq("fromMe", True)
            .gte("data", cutoff)
            .order(id_col, desc=True)
            .limit(1)
            .execute()
            .data
        ) or []
        if not rows:
            return False
        # se a última foi do próprio bot, não bloqueia
        return (rows[0].get("origem") or "").lower() != "bot"
    except Exception:
        return False

# ---- interceptador de pedidos de e-mail ----
_EMAILS = {
    "geral": "contato@lucenera.com.br",
    "thais": "thais@lucenera.com.br",
    "murilo": "murillo@lucenera.com.br",
    "tricia": "tricia@lucenera.com.br",
}

def _intercept_email_request(txt: str) -> str | None:
    """Detecta pedido de e-mail e retorna resposta direta da Julia; senão, None."""
    if not isinstance(txt, str) or "email" not in txt.lower():
        return None
    t = txt.lower()
    if "murilo" in t or "murillo" in t:
        return f"Julia. O e-mail do Murilo é {_EMAILS['murilo']}"
    if "thais" in t or "thaís" in t:
        return f"Julia. O e-mail da Thais é {_EMAILS['thais']}"
    if "tricia" in t or "trícia" in t:
        return f"Julia. O e-mail da Tricia é {_EMAILS['tricia']}"
    return f"Julia. Nosso e-mail geral é {_EMAILS['geral']}"

# -----------------------------
# Exporte explícito para Pylance reconhecer no "import *"
# -----------------------------
__all__ = [
    # base
    "ensure_dir", "ensure_parent", "carrega", "salvar",
    "ler_json", "salvar_json", "guess_mime", "imagem_data_url",
    "to_bool", "only_digits", "clean_phone", "pretty", "clean_env",
    # extras usados pelo app.py
    "_within_business_hours", "_team_is_active", "_intercept_email_request",
]
