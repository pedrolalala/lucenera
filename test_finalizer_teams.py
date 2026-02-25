#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para mensagem que deve ser ignored_finalizer e verificar Teams
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import _save_in_supabase_from_zapi, processar_inline

def test_finalizer_teams():
    """Testa se mensagem finalizer vai para Teams depois de processada"""
    
    # Simular mensagem que deveria ser finalizer
    test_payload = {
        "type": "message",
        "timestamp": "2026-02-12T18:00:00.000000+00:00",
        "from": "556186052453",
        "chatId": "556186052453", 
        "body": "Obrigado!",  # Finalizer típico
        "fromMe": False,
        "instance_id": "test",
        "connected_phone": "5516999999999"
    }
    
    print("=== TESTE MENSAGEM FINALIZER ===")
    print(f"Payload: {test_payload}")
    print("Salvando como received...")
    
    try:
        # Salvar como received
        result = _save_in_supabase_from_zapi(test_payload)
        print(f"Mensagem salva: id_num={result.get('id_num')}")
        
        # Processar para que seja detectado como finalizer
        print("Processando...")
        processar_inline(result)
        
        print("✅ Processamento concluído - verifique se apareceu no Teams como finalizer!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_finalizer_teams()