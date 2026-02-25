"""
Análise abrangente de todos os padrões de conversa para identificar respostas inadequadas
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_all_conversation_patterns():
    """Testa diferentes tipos de conteúdo para identificar respostas inadequadas"""
    
    from main import _humanize_robotic_response
    
    print("=== ANÁLISE ABRANGENTE DE PADRÕES DE CONVERSA ===")
    print()
    
    # Diferentes tipos de mensagens que podem gerar respostas inadequadas
    test_cases = [
        # PROJETO/ILUMINAÇÃO
        {
            "category": "PROJETO/ILUMINAÇÃO",
            "messages": [
                "Bom dia! O projeto da luminária ficou pronto?",
                "Oi, consegue me mandar o layout do gesso?", 
                "Boa tarde! Preciso confirmar os pontos de iluminação",
                "Olá! O beiral vai ter que acrescentar mais perfis?"
            ]
        },
        
        # ESTOQUE/ENTREGA
        {
            "category": "ESTOQUE/ENTREGA", 
            "messages": [
                "Bom dia! Os itens já estão disponíveis no estoque?",
                "Oi, consegue separar o romaneio para retirada?",
                "Boa tarde! Quando posso ir retirar os frames?",
                "Olá! Tem alguma coisa pendente no meu pedido?"
            ]
        },
        
        # TÉCNICAS ESPECÍFICAS
        {
            "category": "TÉCNICAS ESPECÍFICAS",
            "messages": [
                "Bom dia! Qual a potência em watts desse LED?",
                "Oi, que temperatura de cor tem disponível?",
                "Boa tarde! Qual a dimensão desse driver?",
                "Olá! Esse modelo é dimerizável?"
            ]
        },
        
        # PREÇOS E PRAZOS
        {
            "category": "PREÇOS E PRAZOS", 
            "messages": [
                "Bom dia! Qual o preço do perfil L35?",
                "Oi, quanto custa esse orçamento?",
                "Boa tarde! Quando fica pronto o projeto?", 
                "Olá! Tem desconto para fornecedor?"
            ]
        },
        
        # MÍDIA/ARQUIVOS
        {
            "category": "MÍDIA/ARQUIVOS",
            "messages": [
                "Bom dia! Mandei um arquivo por email",
                "Oi, consegue ver a imagem que enviei?",
                "Boa tarde! Te enviei um áudio explicando",
                "Olá! O vídeo mostra o problema"
            ]
        }
    ]
    
    # Simular possíveis respostas inadequadas do ChatGPT
    possible_bad_responses = [
        "**Julia:** Bom dia! Tudo ótimo, e com você?",
        "**Julia:** Boa tarde! Como posso ajudar?", 
        "**Julia:** Oi! Tudo bem? Em que posso auxiliar?",
        "**Julia:** Olá! Tudo certo por aqui, e aí?",
        "**Julia:** Tudo tranquilo, obrigada por perguntar!"
    ]
    
    problems_found = []
    
    for category_data in test_cases:
        category = category_data["category"]
        print(f"📋 CATEGORIA: {category}")
        print("=" * 60)
        
        for i, message in enumerate(category_data["messages"], 1):
            print(f"\n{i}. Mensagem: '{message}'")
            
            # Testar com diferentes respostas ruins do ChatGPT
            for j, bad_response in enumerate(possible_bad_responses, 1):
                print(f"   Teste {j}: ChatGPT disse: '{bad_response}'")
                
                # Aplicar humanização
                corrected = _humanize_robotic_response(bad_response, "Cliente", message)
                
                if corrected != bad_response:
                    print(f"   ✅ CORRIGIDO para: '{corrected[:80]}{'...' if len(corrected) > 80 else ''}'")
                else:
                    print(f"   ❌ NÃO CORRIGIDO (manteve resposta de saudação)")
                    problems_found.append({
                        "category": category,
                        "message": message,
                        "bad_response": bad_response,
                        "issue": "Resposta de saudação para conteúdo técnico não foi corrigida"
                    })
        
        print("\n" + "=" * 60)
        print()
    
    # ANÁLISE DE OUTROS PADRÕES PROBLEMÁTICOS
    print("📊 ANÁLISE DE OUTROS PADRÕES PROBLEMÁTICOS:")
    print("=" * 60)
    
    other_test_cases = [
        # Respostas muito genéricas 
        {
            "message": "Preciso urgente do orçamento da obra",
            "bad_responses": [
                "**Julia:** Entendi sua solicitação, vou verificar",
                "**Julia:** Recebi sua mensagem, vou processar",
                "**Julia:** Compreendo, vou analisar e retornar"
            ]
        },
        
        # Respostas que ignoram contexto de urgência
        {
            "message": "URGENTE: Cliente esperando a entrega hoje",
            "bad_responses": [
                "**Julia:** Vou verificar quando possível",
                "**Julia:** Recebido, vou processar em breve",
                "**Julia:** Ok, vou dar uma olhada"
            ]
        },
        
        # Respostas inadequadas para contexto de problema
        {
            "message": "LED queimou, cliente reclamando, preciso trocar",
            "bad_responses": [
                "**Julia:** Que bom! Vou verificar",
                "**Julia:** Perfeito, vou analisar",
                "**Julia:** Ótimo, recebido"
            ]
        }
    ]
    
    for test_case in other_test_cases:
        print(f"\nMensagem: '{test_case['message']}'")
        
        for bad_response in test_case['bad_responses']:
            corrected = _humanize_robotic_response(bad_response, "Cliente", test_case['message'])
            
            if corrected != bad_response:
                print(f"✅ '{bad_response}' → CORRIGIDO")
            else:
                print(f"❌ '{bad_response}' → NÃO CORRIGIDO")
                problems_found.append({
                    "message": test_case['message'], 
                    "bad_response": bad_response,
                    "issue": "Resposta inadequada para contexto não foi corrigida"
                })
    
    # RESUMO FINAL
    print(f"\n📊 RESUMO FINAL:")
    print(f"   Total de problemas encontrados: {len(problems_found)}")
    
    if problems_found:
        print(f"\n🚨 PROBLEMAS IDENTIFICADOS:")
        for i, problem in enumerate(problems_found[:5], 1):  # Mostrar só os 5 primeiros
            print(f"{i}. {problem['issue']}")
            print(f"   Mensagem: '{problem['message'][:50]}...'")
            print(f"   Resposta ruim: '{problem['bad_response'][:50]}...'")
            
        if len(problems_found) > 5:
            print(f"   ... e mais {len(problems_found) - 5} problemas")

if __name__ == "__main__":
    test_all_conversation_patterns()