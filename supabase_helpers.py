# supabase_helpers.py
import os
from typing import Optional
from supabase_client import supabase

TABLE = "mensagens"
ID_COLUMN = "id"

def _sb_insert(payload: dict) -> Optional[dict]:
    if not supabase:
        return None
    try:
        data = {k: v for k, v in payload.items() if v is not None}
        resp = supabase.table(TABLE).insert(data).execute()
        return (resp.data or [None])[0]
    except Exception as e:
        print(">> Supabase insert erro:", e)
        return None

def _sb_update(id_val, fields: dict) -> Optional[dict]:
    if not supabase:
        return None
    try:
        data = {k: v for k, v in fields.items() if v is not None}
        resp = supabase.table(TABLE).update(data).eq(ID_COLUMN, id_val).execute()
        if resp.data:
            return resp.data[0]
    except Exception as e:
        print(f">> Supabase update erro (col={ID_COLUMN}):", e)
    return None

def _get_row_id(row: dict):
    if not row:
        return None
    return row.get(ID_COLUMN) or row.get("id")