#!/usr/bin/env python3
"""Simple script to call services.zapi_client.send_text_to for a manual test.
Usage: python tools/zapi_send_test.py
"""
from __future__ import annotations
import os
import sys
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
sys.path.insert(0, BASE_DIR)
from services import zapi_client  # noqa: E402

PHONE = os.getenv('TEST_PHONE', 'whatsapp:+5516992089829')
# ensure phone is in plain digits if needed by client
PHONE_PLAIN = '5516992089829'
MSG = 'Teste direto via Z-API (env) - por favor ignore'

if __name__ == '__main__':
    ok = zapi_client.send_text_to(phone=PHONE_PLAIN, message=MSG)
    print('send_text_to returned:', ok)
    if not ok:
        sys.exit(2)
