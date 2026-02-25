"""
Teste direto chamando processar_inline() para ver a resposta REAL das mensagens da Marina
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

def test_marina_direct_processing():
    """Testa as mensagens da Marina chamando diretamente processar_inline()"""
    
    from main import processar_inline, supabase, _supabase_update_safe
    import time
    
    print("=== TESTE DIRETO processar_inline() - MARINA ===")
    print()
    
    if not supabase:
        print("❌ Supabase não disponível")
        return
    
    # As duas mensagens da Marina
    test_cases = [
        {
            "name": "Marina v1 (com 47cm)",
            "mensagem": {
                "text": "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final"
            },
            "telefone": "5516997239080",
            "sender_name": "Escritório Simone Pedreschi Arquitetura - Marina"
        },
        {
            "name": "Marina v2 (sem 47cm)",
            "mensagem": {
                "text": "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final"
            },
            "telefone": "5516997239080", 
            "sender_name": "Escritório Simone Pedreschi Arquitetura - Marina"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"📋 {case['name']}")
        print(f"📞 Telefone: {case['telefone']}")
        print(f"💬 Mensagem: '{case['mensagem']['text']}'")
        print()
        
        try:
            # Criar um row simulado
            row = {
                "id": f"test_{int(time.time())}_{i}",
                "telefone": case['telefone'],
                "sender_name": case['sender_name'],
                "mensagem": case['mensagem'],
                "created_at": "2026-02-12T13:15:00Z",
                "status": "pending",
                "used_ai": False,
                "ai_draft": None
            }
            
            print("🔄 Processando com processar_inline()...")
            
            # Chamar a função diretamente
            processar_inline(row)
            
            print("✅ Processamento concluído")
            
            # Verificar se o row foi modificado
            if "ai_draft" in row and row["ai_draft"]:
                print(f"\n🤖 RESPOSTA REAL GERADA:")
                print(f"   '{row['ai_draft']}'")
            
            if "status" in row:
                print(f"\n🏷️  STATUS FINAL: {row['status']}")
                
            if "analysis" in row:
                print(f"📊 ANÁLISE: {row['analysis']}")
                
        except Exception as e:
            print(f"❌ Erro durante processamento: {e}")
            import traceback
            print(f"📋 Traceback: {traceback.format_exc()}")
            
        print("=" * 80)
        print()

if __name__ == "__main__":
    test_marina_direct_processing()