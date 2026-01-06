#!/usr/bin/env python3
"""Call local /teams/approve?id=<id>&token=<TEAMS_ACTION_TOKEN> to simulate Approve click.
Usage: python tools/approve_local.py <id>
If no id provided, script will try to read last inserted id from stdin.
"""
from __future__ import annotations
import os
import sys
import requests
from dotenv import load_dotenv
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

TEAMS_TOKEN = os.getenv('TEAMS_ACTION_TOKEN', 'troque_por_seu_token_aqui')
PORT = os.getenv('PORT', '5000')
HOST = os.getenv('HOST', '127.0.0.1')

if len(sys.argv) >= 2:
    idval = sys.argv[1]
else:
    print('Usage: python tools\\approve_local.py <id>')
    sys.exit(2)

url = f'http://{HOST}:{PORT}/teams/approve'
params = {'id': idval, 'token': TEAMS_TOKEN}
print('Calling:', url, 'params=', params)
try:
    r = requests.get(url, params=params, timeout=20)
    print('HTTP', r.status_code)
    try:
        print('Response:', r.json())
    except Exception:
        print('Response text:', r.text[:2000])
    sys.exit(0 if r.status_code == 200 else 3)
except Exception as e:
    print('Exception calling approve:', e)
    sys.exit(4)
