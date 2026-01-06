# supabase_client.py — cliente único do Supabase (corrigido)
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, find_dotenv

try:
    from supabase import create_client, Client
except Exception as e:
    raise RuntimeError("Instale a lib: pip install 'supabase>=2.5.1'") from e

# Carrega .env detectado e o local
BASE_DIR = Path(__file__).resolve().parent
fd = find_dotenv()
if fd:
    load_dotenv(fd)
load_dotenv(BASE_DIR / ".env")

def _clean_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    return v.strip().strip('"').strip("'")

SUPABASE_URL = _clean_env("SUPABASE_URL")
SUPABASE_KEY = _clean_env("SUPABASE_SERVICE_ROLE") or _clean_env("SUPABASE_ANON_KEY")

DEFAULT_TABLE = _clean_env("TABLE") or "mensagens"
DEFAULT_IDCOL = _clean_env("ID_COLUMN") or "id_num"

if not SUPABASE_URL or not SUPABASE_KEY:
    print(">> [supabase_client] Faltam SUPABASE_URL e SUPABASE_SERVICE_ROLE/ANON_KEY.")
    supabase: Client | None = None
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(">> [supabase_client] Supabase pronto.")
    except Exception as e:
        print(">> [supabase_client] Falha ao criar client:", e)
        supabase = None

def get_supabase() -> Client | None:
    return supabase

def require_supabase() -> Client:
    if supabase is None:
        raise RuntimeError("Supabase não configurado. Verifique SUPABASE_URL e chave no .env.")
    return supabase

def table(name: Optional[str] = None):
    """
    Atalho para supabase.table('<tabela>').
    NÃO prefixa com 'public.' — o client já usa o schema padrão.
    """
    sb = require_supabase()
    tbl = (name or DEFAULT_TABLE).strip()
    return sb.table(tbl)

def column_exists(tbl: Optional[str], col: str) -> bool:
    try:
        # tenta só selecionar a coluna; se não existir, o PostgREST retorna erro
        _ = table(tbl).select(col).limit(0).execute()
        return True
    except Exception:
        return False

def table_exists(tbl: Optional[str] = None) -> bool:
    try:
        # faz um select * bem leve; se a tabela não existir, vai dar erro
        _ = table(tbl).select("*").limit(1).execute()
        return True
    except Exception:
        return False

def healthcheck(tbl: Optional[str] = None) -> dict:
    info = {
        "url_present": bool(SUPABASE_URL),
        "key_present": bool(SUPABASE_KEY),
        "client_created": supabase is not None,
        "table": (tbl or DEFAULT_TABLE),
        "table_exists": False,
        "id_column_exists": False,
        "note": "",
    }
    if supabase is None:
        info["note"] = "client não criado"
        return info
    t = (tbl or DEFAULT_TABLE)
    try:
        info["table_exists"] = table_exists(t)
        if info["table_exists"]:
            info["id_column_exists"] = column_exists(t, DEFAULT_IDCOL)
        else:
            info["note"] = "tabela não encontrada (ou nome diferente)"
    except Exception as e:
        info["note"] = f"erro ao checar: {type(e).__name__}: {e}"
    return info
