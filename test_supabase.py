# -*- coding: utf-8 -*-
import os
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# 1) garanta que carregamos o .env da pasta lucenera
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import sys

# 2) garante que o diretório do projeto esteja no caminho de import
sys.path.insert(0, str(BASE_DIR))

# 3) mesmo client do app (mesmos tokens e mesma forma de carregar .env)
from supabase_client import supabase

# 3) mesma tabela/coluna que o /admin usa
TABLE = os.getenv("SUPABASE_TABLE") or os.getenv("TABLE_MESSAGES") or "mensagens"
ID_COLUMN = os.getenv("SUPABASE_ID_COLUMN") or "id_num"

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def testar_insercao():
    print(f"=> Tabela: {TABLE} | ID_COLUMN: {ID_COLUMN}")
    # insere um registro de teste
    payload = {
        "telefone": "5511999999999",
        "mensagem": {"text": "Mensagem de teste via test_supabase.py"},
        "nome": {"display": "Teste Local"},
        "data": _now_iso(),
        "status": "received",
        # campos opcionais mas ajudam o painel:
        "group_id": None,
        "group_name": None,
        "used_ai": False,
        "approval_mode": True
    }

    ins = supabase.table(TABLE).insert(payload).execute()
    if not ins or not ins.data:
        print("!! Falha ao inserir (sem data no retorno). Verifique RLS/permissões.")
        return

    row = ins.data[0]
    print(">> Inserido com sucesso:", row)

    # busca os 3 mais recentes para confirmar
    try:
        sel = (supabase.table(TABLE)
               .select("*")
               .order(ID_COLUMN, desc=True)
               .limit(3)
               .execute())
        print(">> Últimos 3 registros:")
        for r in (sel.data or []):
            print({"id": r.get(ID_COLUMN), "tel": r.get("telefone"), "texto": (r.get("mensagem") or {}).get("text"), "data": r.get("data")})
    except Exception as e:
        print("!! Falha ao listar últimos registros:", e)

if __name__ == "__main__":
    testar_insercao()
