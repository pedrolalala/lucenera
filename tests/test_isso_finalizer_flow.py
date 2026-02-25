#!/usr/bin/env python3
"""
Teste prático para verificar se 'isso' é processado como ignored_finalizer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import _save_in_supabase_from_zapi, processar_inline, is_finalizing_message
import time

def test_isso_as_finalizer():
    """
    Testa se uma mensagem 'Isso' é processada como ignored_finalizer.
    """
    print("🧪 Teste: verificando se 'Isso' é detectado como ignored_finalizer...\n")
    
    # Primeiro, testar a função de detecção
    print("1️⃣ Testando detecção básica...")
    is_finalizer = is_finalizing_message("Isso")
    print(f"   is_finalizing_message('Isso'): {is_finalizer}")
    
    if not is_finalizer:
        print("❌ 'Isso' não foi detectado como finalizer!")
        return False
    
    # Payload simulando a mensagem "Isso" do Bruno
    payload = {
        "instanceId": "64a1a0f8-e766-4584-8e07-b79cfaa8e4ac",
        "messageId": "test_isso_finalizer_001",
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
            "message": "Isso"
        },
        "type": "ReceivedCallback"
    }
    
    print(f"\n2️⃣ Simulando mensagem:")
    print(f"   📞 Telefone: {payload['phone']}")
    print(f"   👤 Nome: {payload['senderName']}")  
    print(f"   💬 Mensagem: {payload['text']['message']}")
    print()
    
    # Salvar mensagem
    print("3️⃣ Salvando mensagem como 'received'...")
    row = _save_in_supabase_from_zapi(payload)
    
    if not row:
        print("❌ Falha ao salvar mensagem")
        return False
        
    print(f"   ✅ Mensagem salva. ID: {row.get('id')}, Status: {row.get('status')}")
    
    # Processar mensagem
    print("\n4️⃣ Processando mensagem via processar_inline...")
    print("   (Deve detectar como finalizer e marcar como 'ignored_finalizer')")
    
    try:
        processar_inline(row)
        
        # Verificar o status final da mensagem
        final_status = row.get('status', 'unknown')
        print(f"\n📊 Status final: {final_status}")
        
        if final_status == 'ignored_finalizer':
            print("✅ SUCESSO: Mensagem 'Isso' processada como ignored_finalizer!")
            print("💡 Verificar nos logs se apareceu 'Confirmação/Finalização detectada'")
            return True
        else:
            print(f"❌ FALHA: Status esperado 'ignored_finalizer', recebido '{final_status}'")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro no processamento: {e}")
        return False

if __name__ == "__main__":
    success = test_isso_as_finalizer()
    
    if success:
        print("\n🎉 Teste bem-sucedido! 'Isso' agora é corretamente tratado como finalizer.")
        print("📋 Resultado: Mensagens como 'Isso' não aparecerão mais como 'Aprovação necessária'")
    else:
        print("\n❌ Teste falhou - verificar lógica de processamento")