#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste para processar mensagem received e ver se vai para Teams
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from main import processar_inline, supabase

def test_process_received():
    """Testa se mensagem received vai para Teams depois de processada"""
    
    print("=== TESTE PROCESSAR MENSAGEM RECEIVED ===")
    
    try:
        # Buscar a mensagem mais recente com status received
        response = supabase.table("mensagens").select("*").eq("status", "received").order("id_num", desc=True).limit(1).execute()
        
        if not response.data:
            print("❌ Nenhuma mensagem 'received' encontrada")
            return
            
        row = response.data[0]
        print(f"Mensagem encontrada: id_num={row['id_num']}, texto='{row['mensagem']['text']}'")
        print("Processando...")
        
        processar_inline(row)
        
        # Verificar status após processamento
        response_updated = supabase.table("mensagens").select("*").eq("id_num", row['id_num']).execute()
        if response_updated.data:
            new_status = response_updated.data[0]['status']
            print(f"✅ Processamento concluído! Novo status: {new_status}")
            print("Verifique se apareceu no Teams com o status correto!")
        else:
            print("❌ Erro ao verificar status atualizado")
            
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    test_process_received()