# services/threads.py
# Mantém 1 thread da OpenAI por contato (telefone/grupo) para não misturar histórico.

from __future__ import annotations
from typing import Optional, Dict

# Tenta importar o supabase do seu projeto (se existir)
try:
    from supabase_client import supabase  # seu arquivo já existe na raiz
except Exception:
    supabase = None

from services.openai_helpers import cliente

_THREADS_MEM: Dict[str, str] = {}
TABLE = "threads"  # crie esta tabela para persistir: (id bigserial pk, chave text unique, thread_id text)

def get_or_create_thread_id(chave: Optional[str]) -> str:
    """
    Retorna o thread_id associado à 'chave' (telefone/grupo). Se não existir, cria um novo
    thread na OpenAI e persiste no Supabase (se disponível). Fallback: cache em memória.
    """
    if not chave or not str(chave).strip():
        chave = "anon"
    chave = str(chave)

    # 1) tenta Supabase
    if supabase:
        try:
            res = (supabase.table(TABLE)
                          .select("thread_id")
                          .eq("chave", chave)
                          .limit(1)
                          .execute())
            data = res.data or []
            if data and data[0].get("thread_id"):
                return data[0]["thread_id"]
        except Exception as e:
            print(">> threads.select falhou:", e)

        try:
            t = cliente.beta.threads.create()
            supabase.table(TABLE).insert({"chave": chave, "thread_id": t.id}).execute()
            return t.id
        except Exception as e:
            print(">> threads.insert falhou, usando cache em memória:", e)

    # 2) fallback: memória (não persiste entre reinícios)
    if chave in _THREADS_MEM:
        return _THREADS_MEM[chave]
    t = cliente.beta.threads.create()
    _THREADS_MEM[chave] = t.id
    return t.id
