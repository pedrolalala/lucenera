#!/usr/bin/env python3
"""Fetch ai_draft from a row and send it via services.zapi_client.send_text_to
Usage: python tools/send_ai_draft.py <id>
"""
from __future__ import annotations
import os
import sys
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, '.env'))

try:
    from supabase_client import supabase, DEFAULT_TABLE, DEFAULT_IDCOL
    from services import zapi_client
except Exception as e:
    print('ERROR importing modules:', e)
    sys.exit(2)

if len(sys.argv) < 2:
    print('Usage: python tools/send_ai_draft.py <id>')
    sys.exit(2)

idval = sys.argv[1]
try:
    r = supabase.table(DEFAULT_TABLE).select('*').eq(DEFAULT_IDCOL, idval).limit(1).execute()
    data = r.data or []
    if not data:
        print('No row found')
        sys.exit(3)
    row = data[0]
    phone = row.get('telefone') or row.get('from') or ''
    ai_draft = row.get('ai_draft') or row.get('final_out') or ''
    if phone.startswith('+'):
        phone = phone[1:]
    if phone.startswith('whatsapp:'):
        phone = phone.split('whatsapp:')[-1]
    print('Sending to', phone)
    ok = zapi_client.send_text_to(phone=phone, message=ai_draft)
    print('send text returned', ok)
    sys.exit(0 if ok else 4)
except Exception as e:
    print('ERROR:', e)
    sys.exit(5)
