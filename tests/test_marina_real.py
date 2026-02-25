"""
Teste direto das mensagens da Marina para ver a resposta REAL gerada
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from dotenv import load_dotenv
load_dotenv()

# Importar necessário
from main import app
import json
import time

def test_marina_real_responses():
    """Testa as mensagens da Marina no sistema real"""
    
    # As duas mensagens da Marina
    test_cases = [
        {
            "name": "Marina v1 (com 47cm)",
            "telefone": "5516997239080",
            "mensagem": "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final",
            "nome": "Escritório Simone Pedreschi Arquitetura - Marina"
        },
        {
            "name": "Marina v2 (sem 47cm)",  
            "telefone": "5516997239080",
            "mensagem": "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final",
            "nome": "Escritório Simone Pedreschi Arquitetura - Marina"
        }
    ]
    
    print("=== TESTE REAL DAS MENSAGENS DA MARINA ===")
    print()
    
    # Usar o test client do Flask
    with app.test_client() as client:
        for i, case in enumerate(test_cases, 1):
            print(f"📋 {case['name']}")
            print(f"📞 Telefone: {case['telefone']}")
            print(f"💬 Mensagem: '{case['mensagem']}'")
            print()
            
            # Payload para o endpoint
            payload = {
                "telefone": case['telefone'],
                "mensagem": case['mensagem'],
                "msg_id": f"test_marina_{i}_{int(time.time())}",
                "contexto": {
                    "mensagem_cliente": case['mensagem'],
                    "nome_cliente": case['nome']
                },
                "resposta_bot": None
            }
            
            print("🔄 Processando no sistema real...")
            
            try:
                # Fazer a requisição
                response = client.post('/teams/suggest', 
                                     json=payload,
                                     headers={'Content-Type': 'application/json'})
                
                print(f"📊 Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.get_json()
                    print(f"✅ Response JSON: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                    
                    # Extrair a resposta sugerida se existir
                    if response_data and 'ai_draft' in response_data:
                        ai_response = response_data['ai_draft']
                        print(f"\n🤖 RESPOSTA REAL GERADA:")
                        print(f"   '{ai_response}'")
                    elif response_data and 'status' in response_data:
                        status = response_data['status']
                        print(f"\n🏷️  STATUS: {status}")
                        if status == 'ignored_finalizer':
                            print(f"   🚫 Mensagem foi bloqueada como finalizer")
                        elif status == 'ignored_empty_text':
                            print(f"   🚫 Mensagem foi ignorada como texto vazio")
                    
                else:
                    print(f"❌ Erro: {response.status_code}")
                    print(f"📄 Response: {response.get_data(as_text=True)}")
                    
            except Exception as e:
                print(f"❌ Erro durante teste: {e}")
                
            print("=" * 80)
            print()

if __name__ == "__main__":
    test_marina_real_responses()