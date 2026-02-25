#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para simular mensagem de grupo e verificar se vai para Teams
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import _save_in_supabase_from_zapi

def test_group_message():
    """Testa se mensagem de grupo vai para Teams mesmo sendo ignored_group"""
    
    # Simular mensagem de grupo que fica como 'ignored_group'
    test_payload = {
        "type": "message",
        "timestamp": "2026-02-12T17:58:48.066607+00:00",
        "from": "120363403312144882-group",  # formato de grupo
        "chatId": "120363403312144882-group",
        "body": "Concretagem Concluída 🙏",
        "fromMe": False,
        "instance_id": "test",
        "connected_phone": "5516999999999",
        "sender": {
            "id": "556186052453",
            "name": "Rafael Furlan"
        },
        "isGroup": True,
        "groupName": "Grupo Obra"
    }
    
    print("=== TESTE MENSAGEM DE GRUPO ===")
    print(f"Payload: {test_payload}")
    print("Tentando processar...")
    
    try:
        result = _save_in_supabase_from_zapi(test_payload)
        print(f"Resultado: {result}")
        print("✅ Processamento concluído - verifique se apareceu no Teams!")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_group_message()