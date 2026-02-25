#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para simular mensagem received e verificar se vai para Teams
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import _save_in_supabase_from_zapi

def test_received_message():
    """Testa se mensagem 'received' vai para Teams"""
    
    # Simular mensagem que fica como 'received'
    test_payload = {
        "type": "message",
        "timestamp": "2026-02-12T17:58:48.066607+00:00",
        "from": "556186052453",
        "chatId": "556186052453",
        "body": "Concretagem Concluída 🙏",
        "fromMe": False,
        "instance_id": "test",
        "connected_phone": "5516999999999"
    }
    
    print("=== TESTE MENSAGEM RECEIVED ===")
    print(f"Payload: {test_payload}")
    print("Tentando processar...")
    
    try:
        result = _save_in_supabase_from_zapi(test_payload)
        print(f"Resultado: {result}")
        print("✅ Processamento concluído - verifique se apareceu no Teams!")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_received_message()