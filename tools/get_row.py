#!/usr/bin/env python3
"""Fetch a message row by id_num and print key fields."""
from __future__ import annotations
import os
import sys
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

try:
    from supabase_client import get_supabase_client, DEFAULT_TABLE, DEFAULT_IDCOL  # noqa: E402
except Exception as e:
    print('ERROR importing supabase_client:', e, file=sys.stderr)
    sys.exit(2)

if len(sys.argv) < 2:
    print('Usage: python tools/get_row.py <id>')
    sys.exit(2)

idval = sys.argv[1]
supabase = get_supabase_client()
if supabase is None:
    print('ERROR: Supabase client unavailable (check SUPABASE env vars)', file=sys.stderr)
    sys.exit(2)
try:
    r = supabase.table(DEFAULT_TABLE).select('*').eq(DEFAULT_IDCOL, idval).limit(1).execute()
    data = r.data or []
    if not data:
        print('No row found for id', idval)
        sys.exit(3)
    row = data[0]
    import json
    print(json.dumps(row, ensure_ascii=False, indent=2))
except Exception as e:
    print('ERROR querying supabase:', e, file=sys.stderr)
    sys.exit(4)
