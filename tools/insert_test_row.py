#!/usr/bin/env python3
"""Insert a test row into the Supabase 'mensagens' table and print the inserted id.

Usage:
    python tools/insert_test_row.py
"""
from datetime import datetime, timezone
import json
import sys

try:
    from supabase_client import supabase, DEFAULT_TABLE, DEFAULT_IDCOL
except Exception as e:
    print("ERROR: cannot import supabase_client:", e)
    sys.exit(2)

if supabase is None:
    print("ERROR: supabase client not configured in .env")
    sys.exit(2)

now = datetime.now(timezone.utc).isoformat()
row = {
    "telefone": "5516997000842",
    "mensagem": {"text": "Teste de approve via Teams (script)", "meta": {}},
    "data": now,
    "ai_draft": "Mensagem de teste enviada via Teams approve",
    "used_ai": False,
    "approval_mode": True,
    "status": "awaiting_approval"
}

try:
    out = supabase.table(DEFAULT_TABLE).insert(row).execute()
    data = out.data or []
    if not data:
        print("ERROR: insert returned empty. Response:", out, file=sys.stderr)
        sys.exit(3)
    inserted = data[0]
    # print inserted id column if present
    idcol = DEFAULT_IDCOL
    idval = inserted.get(idcol) or inserted.get("id") or json.dumps(inserted)
    print(idval)
except Exception as e:
    print("ERROR: failed to insert row:", e, file=sys.stderr)
    sys.exit(4)
