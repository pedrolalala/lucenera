#!/usr/bin/env python3
"""
Teste específico para o caso do Bruno Cisotto.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import _save_in_supabase_from_zapi, processar_inline
import time

def test_bruno_cisotto_case():
    """
    Testa o caso específico do Bruno Cisotto que deveria gerar:
    "Vou consultar a entrega de material e te retorno"
    """
    print("🧪 Teste: caso específico Bruno Cisotto sobre entrega...\n")
    
    # Payload simulando a mensagem do Bruno Cisotto
    payload = {
        "instanceId": "64a1a0f8-e766-4584-8e07-b79cfaa8e4ac",
        "messageId": "test_bruno_cisotto_entrega",
        "phone": "5516999613340",
        "fromMe": False,
        "momment": int(time.time()),
        "status": "received",
        "chatId": "5516999613340@c.us",
        "senderName": "Bruno Cisotto",
        "senderPhoto": "",
        "isGroup": False,
        "isGroupPost": False,
        "instanceName": "lucenera",
        "text": {
            "message": "Confirmada a entrega do material hoje?"
        },
        "type": "ReceivedCallback"
    }
    
    print(f"📥 Simulando mensagem do Bruno Cisotto:")
    print(f"   📞 Telefone: {payload['phone']}")
    print(f"   👤 Nome: {payload['senderName']}")  
    print(f"   💬 Mensagem: {payload['text']['message']}")
    print()
    
    # Salvar mensagem
    print("1️⃣ Salvando mensagem como 'received'...")
    row = _save_in_supabase_from_zapi(payload)
    
    if not row:
        print("❌ Falha ao salvar mensagem")
        return False
        
    print(f"   ✅ Mensagem salva. ID: {row.get('id')}, Status: {row.get('status')}")
    
    # Processar mensagem
    print("\n2️⃣ Processando mensagem via processar_inline...")
    
    try:
        processar_inline(row)
        
        # Verificar a resposta gerada
        ai_draft = row.get("ai_draft") or ""
        
        print(f"\n📊 Resposta AI gerada: '{ai_draft}'")
        
        # Verificar se contém as palavras corretas
        expected_words = ["entrega", "material"]
        wrong_words = ["valores", "prazos"]
        
        has_correct = all(word in ai_draft.lower() for word in expected_words)
        has_wrong = any(word in ai_draft.lower() for word in wrong_words)
        
        if has_correct and not has_wrong:
            print("✅ SUCESSO: Resposta correta sobre entrega de material!")
            print(f"   ✓ Contém: {expected_words}")
            print(f"   ✗ Não contém: {wrong_words}")
            return True
        elif has_wrong:
            print("❌ FALHA: Ainda contém palavras sobre preços/prazos")
            print(f"   ❌ Resposta incorreta: '{ai_draft}'")
            return False
        elif not has_correct:
            print("❌ FALHA: Não contém palavras esperadas sobre entrega")
            print(f"   ❌ Resposta: '{ai_draft}'")
            return False
        else:
            print("⚠️ Resultado inesperado")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro no processamento: {e}")
        return False

if __name__ == "__main__":
    success = test_bruno_cisotto_case()
    
    if success:
        print("\n🎉 Teste bem-sucedido! Caso Bruno Cisotto agora gera resposta correta.")
        print("📋 'Confirmada a entrega do material hoje?' → resposta sobre ENTREGA (não preços)")
    else:
        print("\n❌ Teste falhou - verificar lógica de detecção")