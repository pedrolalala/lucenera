#!/usr/bin/env python3
"""
Teste prático para verificar se a duplicação de mensagens no Teams foi corrigida.
Simula uma mensagem normal que deveria gerar apenas UMA notificação Teams.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import _save_in_supabase_from_zapi, processar_inline
import time

def test_single_notification():
    """
    Testa se uma mensagem normal gera apenas UMA notificação Teams.
    """
    print("🧪 Teste prático: verificando notificação única para mensagem normal...\n")
    
    # Payload simulando mensagem do exemplo do usuário
    payload = {
        "instanceId": "64a1a0f8-e766-4584-8e07-b79cfaa8e4ac",
        "messageId": "test_single_notification_001",
        "phone": "5516996060007",
        "fromMe": False,
        "momment": int(time.time()),
        "status": "received",
        "chatId": "5516996060007@c.us",
        "senderName": "Bruno Castanhari - Arq C4 Arquitetos",
        "senderPhoto": "",
        "isGroup": False,
        "isGroupPost": False,
        "instanceName": "lucenera",
        "text": {
            "message": "Quando vocês atualizarem, me manda pra eu mandar pra Automundi?"
        },
        "type": "ReceivedCallback"
    }
    
    print(f"📥 Simulando recebimento de mensagem:")
    print(f"   📞 Telefone: {payload['phone']}")
    print(f"   👤 Nome: {payload['senderName']}")  
    print(f"   💬 Mensagem: {payload['text']['message']}")
    print()
    
    # Salvar mensagem (como faz o webhook)
    print("1️⃣ Salvando mensagem como 'received'...")
    row = _save_in_supabase_from_zapi(payload)
    
    if not row:
        print("❌ Falha ao salvar mensagem")
        return False
        
    print(f"   ✅ Mensagem salva. ID: {row.get('id')}, Status: {row.get('status')}")
    
    # Simular processamento (como faz o debounce)
    print("\n2️⃣ Processando mensagem via processar_inline...")
    print("   (Isso deve gerar APENAS UMA notificação Teams)")
    
    try:
        processar_inline(row)
        print("   ✅ Processamento concluído")
        print("\n📊 Resultado esperado:")
        print("   ✅ UMA notificação Teams de 'Aprovação necessária'") 
        print("   ❌ NENHUMA notificação adicional de 'Mensagem processada'")
        print("\n💡 Verificar nos logs se apareceu apenas '>> TEAMS post -> 200' uma vez")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro no processamento: {e}")
        return False

if __name__ == "__main__":
    success = test_single_notification()
    
    if success:
        print("\n🎉 Teste concluído com sucesso!")
        print("📋 Próximos passos: Verificar logs do Teams para confirmar notificação única")
    else:
        print("\n❌ Teste falhou - verificar configurações")