#!/usr/bin/env python3
"""
Script para verificar e processar mensagens pendentes de um número específico.
"""

import sys
import os
from typing import Dict, Any
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import processar_inline, supabase, ID_COLUMN, _digits_only
from datetime import datetime

def check_pending_messages(phone_number: str):
    """
    Verifica mensagens pendentes (status=received) para um número específico.
    """
    if not supabase:
        print("❌ Supabase não disponível")
        return
        
    phone_normalized = _digits_only(phone_number)
    print(f"🔍 Verificando mensagens pendentes para: {phone_normalized}")
    
    try:
        # Buscar mensagens com status 'received' para este telefone
        result = supabase.table("mensagens") \
            .select("*") \
            .eq("telefone", phone_normalized) \
            .eq("status", "received") \
            .order("id_num", desc=True) \
            .limit(5) \
            .execute()
        
        if not result.data:
            print("✅ Nenhuma mensagem pendente encontrada")
            return
            
        print(f"📋 Encontradas {len(result.data)} mensagens pendentes:")
        
        for i, row in enumerate(result.data, 1):
            if not isinstance(row, dict):
                continue
            created_at = row.get("created_at", "")
            mensagem = row.get("mensagem")
            if isinstance(mensagem, dict):
                text_value = mensagem.get("text") or ""
                text = str(text_value).strip()[:80] if text_value else ""
            else:
                text = ""
            row_id = row.get(ID_COLUMN)
            
            print(f"  {i}. ID: {row_id}")
            print(f"     📅 {created_at}")
            print(f"     💬 {text}")
            print()
            
        # Oferecer para processar as mensagens
        choice = input("🤖 Deseja processar essas mensagens agora? (s/n): ").lower()
        
        if choice in ['s', 'sim', 'y', 'yes']:
            print("\n🚀 Processando mensagens...")
            
            for i, row in enumerate(result.data, 1):
                if not isinstance(row, dict):
                    continue
                row_id = row.get(ID_COLUMN)
                mensagem = row.get("mensagem")
                if isinstance(mensagem, dict):
                    text_value = mensagem.get("text") or ""
                    text = str(text_value).strip()[:50] if text_value else ""
                else:
                    text = ""
                
                print(f"  {i}/{len(result.data)} Processando ID {row_id}: {text}...")
                
                try:
                    processar_inline(row)
                    print(f"     ✅ Processada com sucesso")
                except Exception as e:
                    print(f"     ❌ Erro: {e}")
                    
            print("\n🎉 Processamento concluído!")
        else:
            print("ℹ️ Processamento cancelado pelo usuário")
            
    except Exception as e:
        print(f"❌ Erro ao verificar mensagens: {e}")

if __name__ == "__main__":
    # Usar o número do usuário
    phone = "5517996772898"  # Eq. Isabela - Solange Calio
    check_pending_messages(phone)