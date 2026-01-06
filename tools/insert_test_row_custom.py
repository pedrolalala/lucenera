#!/usr/bin/env python3
"""Insert a test row into Supabase using TEST_PHONE from .env (or CUSTOM_TEST_PHONE).
Prints the inserted id.
"""
from __future__ import annotations
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

CUSTOM = os.getenv('CUSTOM_TEST_PHONE')
TEST_PHONE = os.getenv('TEST_PHONE')
if CUSTOM:
    phone_raw = CUSTOM
elif TEST_PHONE:
    phone_raw = TEST_PHONE
else:
    print('ERROR: set TEST_PHONE or CUSTOM_TEST_PHONE in .env', file=sys.stderr)
    sys.exit(2)

# normalize to digits only if starts with whatsapp:
if phone_raw.startswith('whatsapp:'):
    phone = phone_raw.split('whatsapp:')[-1]
elif phone_raw.startswith('+'):
    phone = phone_raw[1:]
else:
    phone = phone_raw

try:
    from supabase_client import supabase, DEFAULT_TABLE
except Exception as e:
    print('ERROR importing supabase_client:', e, file=sys.stderr)
    sys.exit(3)

now = datetime.now(timezone.utc).isoformat()
row = {
    'telefone': phone,
    'mensagem': {'text': 'Teste E2E: enviar ai_draft por approve', 'meta': {}},
    'data': now,
    'ai_draft': 'Esta é uma resposta automática gerada pela IA para teste. Por favor ignore.',
    'used_ai': False,
    'approval_mode': True,
    'status': 'awaiting_approval'
}

try:
    out = supabase.table(DEFAULT_TABLE).insert(row).execute()
    data = out.data or []
    if not data:
        print('ERROR: insert returned empty. Response:', out, file=sys.stderr)
        sys.exit(4)
    inserted = data[0]
    # print id column
    idcol = 'id_num'
    idval = inserted.get(idcol) or inserted.get('id') or inserted
    print(idval)
except Exception as e:
    print('ERROR: failed to insert row:', e, file=sys.stderr)
    sys.exit(5)
