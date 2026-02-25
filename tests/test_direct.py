"""
Teste direto sem passar pelo servidor HTTP
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

# Importar o app Flask
from main import app

# Importar o cliente de teste do Flask
with app.test_client() as client:
    print("🔄 Testando endpoint DIRETAMENTE via Flask test client...")
    
    payload = {
        "telefone": "5516999999999",
        "mensagem": "Teste direto via test client",
        "msg_id": "test_direct_001",
        "contexto": {"mensagem_cliente": "Teste"},
        "resposta_bot": "Bot respondeu"
    }
    
    response = client.post('/teams/suggest', json=payload)
    
    print(f"\n📊 Status Code: {response.status_code}")
    print(f"📄 Response JSON: {response.get_json()}")
    print(f"📋 Response Headers: {dict(response.headers)}")
