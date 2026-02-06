
import sys
sys.path.insert(0, '.')
import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()
BASE_URL = "http://localhost:5000"

def test_suggest_sucesso():
    payload = {
        "telefone": "5516999999999",
        "mensagem": "[TESTE E2E] Resposta corrigida pelo sistema automatizado",
        "msg_id": "test_e2e_001",
        "contexto": {
            "mensagem_cliente": "Cliente perguntou sobre projeto luminotécnico",
            "resposta_bot": "Vou verificar"
        },
        "resposta_bot": "Vou verificar",
        "token": os.getenv("TEAMS_ACTION_TOKEN")
    }
    print(f"🔄 Testando endpoint POST /teams/suggest (Cenário: Sucesso)")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    try:
        response = requests.post(f"{BASE_URL}/teams/suggest", json=payload, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Resposta: {json.dumps(response.json(), indent=2)}\n")
        assert response.status_code == 200, f"Status esperado 200, recebido {response.status_code}"
        data = response.json()
        assert data.get('success') == True, "Campo 'success' deveria ser True"
        assert data.get('enviada_whatsapp') == True, "Campo 'enviada_whatsapp' deveria ser True"
        assert data.get('registrada_supabase') == True, "Campo 'registrada_supabase' deveria ser True"
        assert data.get('telefone') == "5516999999999", "Telefone não corresponde"
        print("✅ Teste de sucesso PASSOU\n")
        return True
    except AssertionError as e:
        print(f"❌ FALHA NA VALIDAÇÃO: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ ERRO ao executar teste: {str(e)}")
        return False

def test_suggest_payload_invalido():
    casos_teste = [
        {"nome": "Telefone ausente", "payload": {"mensagem": "Teste", "token": os.getenv("TEAMS_ACTION_TOKEN")}, "status_esperado": 400, "erro_esperado": "Campos obrigatórios ausentes"},
        {"nome": "Mensagem vazia", "payload": {"telefone": "5516999999999", "mensagem": "   ", "token": os.getenv("TEAMS_ACTION_TOKEN")}, "status_esperado": 400, "erro_esperado": "Mensagem não pode estar vazia"},
        {"nome": "Telefone inválido", "payload": {"telefone": "123", "mensagem": "Teste", "token": os.getenv("TEAMS_ACTION_TOKEN")}, "status_esperado": 400, "erro_esperado": "Formato de telefone inválido"},
    ]
    falhas = []
    for caso in casos_teste:
        print(f"🔄 Testando: {caso['nome']}")
        try:
            response = requests.post(f"{BASE_URL}/teams/suggest", json=caso['payload'], timeout=10)
            if response.status_code == caso['status_esperado']:
                if caso['erro_esperado'] in response.text:
                    print(f"✅ {caso['nome']} - Validação OK\n")
                else:
                    print(f"❌ {caso['nome']} - Erro diferente do esperado")
                    falhas.append(caso['nome'])
            else:
                print(f"❌ {caso['nome']} - Status {response.status_code}, esperado {caso['status_esperado']}")
                falhas.append(caso['nome'])
        except Exception as e:
            print(f"❌ {caso['nome']} - Exceção: {str(e)}")
            falhas.append(caso['nome'])
    if falhas:
        print(f"\n🔧 CORREÇÃO NECESSÁRIA nas validações: {falhas}")
        return False
    print("✅ Todos os testes de validação PASSARAM\n")
    return True

if __name__ == '__main__':
    test_suggest_sucesso()
    test_suggest_payload_invalido()
