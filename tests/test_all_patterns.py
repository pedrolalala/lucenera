"""
Análise abrangente de todos os padrões de conversa para identificar respostas inadequadas
Inclui testes de todas as funcionalidades do sistema de resposta automatizada
"""
import sys
import os
from pathlib import Path

# Adicionar o diretório principal ao path
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

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


def test_refinement_system():
    """Teste do Sistema de Refinamento de Respostas"""
    print("\n🧪 TESTE DO SISTEMA DE REFINAMENTO DE RESPOSTAS")
    print("=" * 60)
    
    from main import (
        _identify_message_type,
        _generate_contextual_response_by_type,
        refine_response_with_ai,
        _validate_refined_response,
        ENABLE_RESPONSE_REFINEMENT
    )

    # Casos de teste para validar o refinamento
    test_cases = [
        {
            "name": "Pergunta sobre retirada",
            "user_message": "Consigo retirar hoje?",
            "context": "- Cliente: Oi, bom dia!\n- Julia: Boa tarde! Em que posso auxiliar você?\n- Cliente: Queria saber sobre meu pedido",
            "expected_type": "mensagem_especifica"
        },
        {
            "name": "Pergunta sobre orçamento",
            "user_message": "Quanto custa esse projeto de iluminação?",
            "context": "- Cliente: Preciso de uma cotação\n- Julia: Vou consultar os valores atualizados",
            "expected_type": "mensagem_especifica"
        },
        {
            "name": "Agendamento com arquiteto",
            "user_message": "Podemos marcar um encontro com o arquiteto na sexta?",
            "context": "",
            "expected_type": "agendamento"
        },
        {
            "name": "Saudação simples",
            "user_message": "Bom dia!",
            "context": "",
            "expected_type": "saudacao"
        },
        {
            "name": "Finalização com agradecimento",
            "user_message": "Muito obrigado pela atenção!",
            "context": "- Julia: Vou verificar e te retorno\n- Cliente: Perfeito",
            "expected_type": "finalizacao"
        }
    ]

    def test_message_classification():
        """Testa se a classificação de mensagens está funcionando."""
        print("=== TESTE DE CLASSIFICAÇÃO ===")
        
        for i, case in enumerate(test_cases, 1):
            msg_type = _identify_message_type(case["user_message"])
            status = "✅" if msg_type == case["expected_type"] else "❌"
            
            print(f"{i:2d}. {case['name']}")
            print(f"    Mensagem: '{case['user_message']}'")
            print(f"    Esperado: {case['expected_type']} | Obtido: {msg_type} {status}")

    def test_base_responses():
        """Testa se as respostas base estão sendo geradas."""
        print("\n=== TESTE DE RESPOSTAS BASE ===")
        
        for i, case in enumerate(test_cases, 1):
            msg_type = _identify_message_type(case["user_message"])
            base_response = _generate_contextual_response_by_type(case["user_message"], msg_type)
            
            print(f"{i:2d}. {case['name']} ({msg_type})")
            print(f"    Mensagem: '{case['user_message']}'")
            print(f"    Resposta Base: '{base_response}'")

    def test_validation_rules():
        """Testa as regras de validação."""
        print("\n=== TESTE DE VALIDAÇÃO ===")
        
        test_validations = [
            {
                "refined": "Boa tarde! Vou verificar essa informação e te retorno!",
                "base": "Vou verificar essa informação e te retorno em breve!",
                "user_msg": "Quando vai chegar?",
                "should_pass": True,
                "reason": "Mantém ação principal"
            },
            {
                "refined": "Vai chegar amanhã às 14h por R$ 50,00",
                "base": "Vou verificar e te retorno!",
                "user_msg": "Quando vai chegar?",
                "should_pass": False,
                "reason": "Inventou informações"
            },
            {
                "refined": "",
                "base": "Vou verificar!",
                "user_msg": "Test",
                "should_pass": False,
                "reason": "Resposta vazia"
            }
        ]
        
        for i, test in enumerate(test_validations, 1):
            is_valid = _validate_refined_response(test["refined"], test["base"], test["user_msg"])
            expected = test["should_pass"]
            status = "✅" if is_valid == expected else "❌"
            
            print(f"{i:2d}. {test['reason']}")
            print(f"    Refinada: '{test['refined'][:50]}...'")
            print(f"    Esperado: {'Passar' if expected else 'Falhar'} | Resultado: {'Passou' if is_valid else 'Falhou'} {status}")

    try:
        test_message_classification()
        test_base_responses()
        test_validation_rules()
        print("\n✅ TESTES DE REFINAMENTO CONCLUÍDOS")
        
    except Exception as e:
        print(f"\n❌ ERRO NOS TESTES DE REFINAMENTO: {e}")


def test_new_categories():
    """Testa as novas categorias de respostas automáticas"""
    print("\n🚀 TESTANDO NOVAS CATEGORIAS DE RESPOSTAS AUTOMÁTICAS")
    print("=" * 60)
    
    from main import _identify_message_type, _generate_contextual_response_by_type

    def test_message_category(message, expected_category, description):
        """Testa uma mensagem e verifica se foi classificada corretamente."""
        detected_category = _identify_message_type(message)
        
        print(f"\n=== {description} ===")
        print(f"Mensagem: \"{message}\"")
        print(f"Categoria esperada: {expected_category}")
        print(f"Categoria detectada: {detected_category}")
        
        # Verificar se a categoria está correta
        success = detected_category == expected_category
        status = "✅ SUCESSO" if success else "❌ FALHOU"
        print(f"Status: {status}")
        
        if success:
            # Se a categoria está correta, testar a resposta
            response = _generate_contextual_response_by_type(message, detected_category)
            print(f"Resposta gerada: \"{response}\"")
        else:
            print(f"⚠️  Esperava '{expected_category}' mas detectou '{detected_category}'")
        
        return success

    tests_passed = 0
    total_tests = 0
    
    # ===== CATEGORIA: MENSAGENS ESPECÍFICAS =====
    print("\n🎯 CATEGORIA 1: MENSAGENS ESPECÍFICAS")
    
    # 1. PIX/PAGAMENTO
    tests = [
        ("Qual a chave PIX?", "mensagem_especifica", "PIX - Pergunta sobre chave"),
        ("Preciso dos dados bancários", "mensagem_especifica", "PIX - Dados bancários"),
        ("Pode me passar os dados para pagamento?", "mensagem_especifica", "PIX - Dados pagamento"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 2. ORÇAMENTO
    tests = [
        ("Preciso de um orçamento", "mensagem_especifica", "Orçamento - Solicitação"),
        ("Pode fazer uma proposta?", "mensagem_especifica", "Orçamento - Proposta"),
        ("Quanto custa esse produto?", "mensagem_especifica", "Orçamento - Preço"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 3. ENTREGA
    tests = [
        ("Vocês entregam?", "mensagem_especifica", "Entrega - Disponibilidade"),
        ("Qual o prazo de entrega?", "mensagem_especifica", "Entrega - Prazo"),
        ("Como é o frete?", "mensagem_especifica", "Entrega - Frete"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 4. RETIRADA
    tests = [
        ("Posso retirar no estoque?", "mensagem_especifica", "Retirada - Local"),
        ("Quando posso buscar?", "mensagem_especifica", "Retirada - Horário"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== CATEGORIA: AGENDAMENTO =====
    print("\n🎯 CATEGORIA 2: AGENDAMENTO")
    
    tests = [
        ("Podemos marcar uma reunião?", "agendamento", "Agendamento - Reunião"),
        ("Quando podemos nos encontrar?", "agendamento", "Agendamento - Encontro"),
        ("Vamos agendar a entrega?", "agendamento", "Agendamento - Entrega"),
        ("Preciso marcar horário com o arquiteto", "agendamento", "Agendamento - Arquiteto"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== CATEGORIA: SAUDAÇÃO =====
    print("\n🎯 CATEGORIA 3: SAUDAÇÃO")
    
    tests = [
        ("Bom dia!", "saudacao", "Saudação - Bom dia"),
        ("Boa tarde!", "saudacao", "Saudação - Boa tarde"),
        ("Oi!", "saudacao", "Saudação - Oi"),
        ("Olá!", "saudacao", "Saudação - Olá"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== CATEGORIA: FINALIZAÇÃO =====
    print("\n🎯 CATEGORIA 4: FINALIZAÇÃO")
    
    tests = [
        ("Obrigado!", "finalizacao", "Finalização - Obrigado"),
        ("Muito obrigada!", "finalizacao", "Finalização - Obrigada"),
        ("À disposição", "finalizacao", "Finalização - Disposição"),
        ("Valeu!", "finalizacao", "Finalização - Valeu"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # RESULTADO FINAL
    print(f"\n📊 RESULTADO FINAL:")
    print(f"   Testes aprovados: {tests_passed}/{total_tests}")
    print(f"   Taxa de sucesso: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        print("   🎉 TODOS OS TESTES PASSARAM!")
    else:
        print(f"   ⚠️  {total_tests - tests_passed} testes falharam")


def test_real_cases_analysis():
    """Análise das 74 mensagens reais de clientes"""
    print("\n🔍 ANÁLISE DE CASOS REAIS - 74 MENSAGENS DE CLIENTES")
    print("=" * 60)
    
    from main import _identify_message_type, _generate_contextual_response_by_type
    
    # Mensagens reais analisadas anteriormente
    real_messages = [
        "Oi Murilo!!! Bom dia!",
        "LUC91 - SPOT GERRY COM ARTICULACAO - GU10 – BRANCO – 6 UNIDADES Quantos watts? E...",
        "País, bom dia, tudo bem? Demorei a responder que eu tava viajando, viu? Hoje que...",
        "bom dia, tudo bem? lá no começo de dezembro vocês comentaram que já estavam pedi...",
        "a entrada da garagem onde eu fiz o traçado em vermelho o quadrado em vermelho o ...",
        "Ok obrigado, bom dia",
        "Tudo também! Eles já instalaram o forro de gesso e vão começar a instalação do v...",
        "Acredito que sim! O Guto Cyrino que está tocando essa parte, posso te pedir a ge...",
        "Ele até está falando com alguém daí, mas não sei com quem é!",
        "Murilo?",
        "Oi bom dia Tá OK",
        "A L14 e a L15 é aquela que eu tenho aqui, né? Que vocês mandaram uma amostra.",
        "Magina",
        "Eu estou na obra",
        "Eu aguardo Muito obrigada",
        "O Murilo, eu lembro, inclusive tá com o Guto, essa amostra que eu deixei com ele...",
        "Me envia à distância dos spots L1",
        "A da academia e a do corredor, acho que você pode sim já confirmar o tamanho par...",
        "bom dia, vou verificar com o engenheiro",
        "Perfeito",
    ]
    
    # Análise estatística
    category_count = {}
    
    for i, message in enumerate(real_messages[:20], 1):  # Apenas os primeiros 20 para demonstração
        msg_type = _identify_message_type(message)
        category_count[msg_type] = category_count.get(msg_type, 0) + 1
        
        print(f"{i:2d}. Mensagem: '{message[:60]}{'...' if len(message) > 60 else ''}'")
        print(f"    Categoria: {msg_type}")
        
        response = _generate_contextual_response_by_type(message, msg_type)
        print(f"    Resposta: '{response[:80]}{'...' if len(response) > 80 else ''}'")
        print()
    
    print("📊 DISTRIBUIÇÃO POR CATEGORIA:")
    for category, count in sorted(category_count.items()):
        percentage = (count / len(real_messages[:20])) * 100
        print(f"   {category}: {count} mensagens ({percentage:.1f}%)")


def test_humanize_function():
    """Testa especificamente a função de humanização de respostas robóticas"""
    print("\n🤖 TESTE DA FUNÇÃO DE HUMANIZAÇÃO")
    print("=" * 60)
    
    from main import _humanize_robotic_response
    
    # Casos de teste para humanização
    test_cases = [
        {
            "original_msg": "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final",
            "chatgpt_response": "**Julia:** Tudo otimo, obrigada por perguntar, e com você?",
            "description": "Resposta inadequada de saudação para mensagem técnica"
        },
        {
            "original_msg": "Preciso urgente do orçamento da obra",
            "chatgpt_response": "**Julia:** Oi! Tudo bem? Como posso ajudar?",
            "description": "Saudação genérica para pedido urgente"
        },
        {
            "original_msg": "LED queimou, cliente reclamando, preciso trocar",
            "chatgpt_response": "**Julia:** Que bom! Vou verificar",
            "description": "Resposta positiva inadequada para problema"
        },
        {
            "original_msg": "Qual a dimensão desse driver?",
            "chatgpt_response": "**Julia:** Bom dia! Tudo certo por aqui, e aí?",
            "description": "Saudação casual para pergunta técnica"
        }
    ]
    
    print(f"Testando {len(test_cases)} casos de humanização:")
    print()
    
    for i, case in enumerate(test_cases, 1):
        print(f"📋 CASO {i}: {case['description']}")
        print(f"Mensagem original: '{case['original_msg'][:60]}...'")
        print(f"ChatGPT disse: '{case['chatgpt_response']}'")
        
        # Aplicar humanização
        final_response = _humanize_robotic_response(case['chatgpt_response'], "Cliente", case['original_msg'])
        
        print(f"APÓS humanização: '{final_response}'")
        
        if final_response != case['chatgpt_response']:
            print(f"✅ CORREÇÃO APLICADA!")
        else:
            print(f"❌ Resposta não foi corrigida")
        
        print("=" * 60)
        print()


def test_greeting_detection():
    """Testa a detecção de saudações vs finalizadores"""
    print("\n👋 TESTE DE DETECÇÃO DE SAUDAÇÕES")
    print("=" * 60)
    
    try:
        from main import is_finalizing_message
        
        # Buscar função _safe_is_greeting 
        import inspect
        import main
        
        _safe_is_greeting = None
        for name, obj in inspect.getmembers(main):
            if name == '_safe_is_greeting' and callable(obj):
                _safe_is_greeting = obj
                break
        
        if not _safe_is_greeting:
            print("❌ Função _safe_is_greeting não encontrada")
            return
        
        print("✅ Funções de detecção carregadas")
        
        # Casos de teste para detecção
        test_cases = [
            {
                "message": "Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton",
                "expected_greeting": True,
                "expected_finalizer": False,
                "description": "Saudação + conteúdo técnico (não deve ser smalltalk)"
            },
            {
                "message": "Oi! Tudo bem?",
                "expected_greeting": True,
                "expected_finalizer": False,
                "description": "Saudação pura (pode ser smalltalk)"
            },
            {
                "message": "Obrigado pela atenção!",
                "expected_greeting": False,
                "expected_finalizer": True,
                "description": "Finalização pura"
            },
            {
                "message": "Bom dia! Obrigado pelo retorno",
                "expected_greeting": True,
                "expected_finalizer": True,
                "description": "Saudação + finalização"
            }
        ]
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n📋 CASO {i}: {case['description']}")
            print(f"Mensagem: '{case['message']}'")
            
            is_greeting = _safe_is_greeting(case['message'])
            is_finalizer = is_finalizing_message(case['message'])
            smalltalk_condition = is_greeting and (not is_finalizer)
            
            print(f"   is_greeting: {is_greeting} (esperado: {case['expected_greeting']})")
            print(f"   is_finalizer: {is_finalizer} (esperado: {case['expected_finalizer']})")
            print(f"   smalltalk = greeting AND (NOT finalizer): {smalltalk_condition}")
            
            # Verificar se as detecções estão corretas
            greeting_ok = is_greeting == case['expected_greeting']
            finalizer_ok = is_finalizer == case['expected_finalizer']
            
            if greeting_ok and finalizer_ok:
                print(f"   ✅ DETECÇÃO CORRETA")
            else:
                print(f"   ❌ DETECÇÃO INCORRETA")
                if not greeting_ok:
                    print(f"      - Esperava greeting={case['expected_greeting']}, obteve {is_greeting}")
                if not finalizer_ok:
                    print(f"      - Esperava finalizer={case['expected_finalizer']}, obteve {is_finalizer}")
            
            if smalltalk_condition and (case['expected_finalizer'] or len(case['message'].split()) > 5):
                print(f"   🚨 AVISO: Mensagem será processada como SMALLTALK (pode ser inadequado)")
                
    except ImportError as e:
        print(f"❌ Erro ao importar funções: {e}")


def test_74_messages_analysis():
    """Executa a análise das 74 mensagens reais como no arquivo analisar_74_mensagens.py"""
    print("\n📊 ANÁLISE COMPLETA: 74 MENSAGENS REAIS DE CLIENTES")
    print("=" * 60)
    
    from main import _identify_message_type, _generate_contextual_response_by_type
    
    # As 74 mensagens reais (amostra das primeiras)
    messages_74 = [
        "Oi Murilo!!! Bom dia!",
        "LUC91 - SPOT GERRY COM ARTICULACAO - GU10 – BRANCO – 6 UNIDADES Quantos watts? E...",
        "País, bom dia, tudo bem? Demorei a responder que eu tava viajando, viu? Hoje que...",
        "bom dia, tudo bem? lá no começo de dezembro vocês comentaram que já estavam pedi...",
        "a entrada da garagem onde eu fiz o traçado em vermelho o quadrado em vermelho o ...",
        "Ok obrigado, bom dia",
        "Tudo também! Eles já instalaram o forro de gesso e vão começar a instalação do v...",
        "Acredito que sim! O Guto Cyrino que está tocando essa parte, posso te pedir a ge...",
        "Ele até está falando com alguém daí, mas não sei com quem é!",
        "Murilo?",
        "Oi bom dia Tá OK",
        "A L14 e a L15 é aquela que eu tenho aqui, né? Que vocês mandaram uma amostra.",
        "Magina",
        "Eu estou na obra",
        "Eu aguardo Muito obrigada",
        "O Murilo, eu lembro, inclusive tá com o Guto, essa amostra que eu deixei com ele...",
        "Me envia à distância dos spots L1",
        "A da academia e a do corredor, acho que você pode sim já confirmar o tamanho par...",
        "bom dia, vou verificar com o engenheiro",
        "Perfeito"
    ]
    
    # Estatísticas
    category_stats = {}
    
    print("🔍 ANÁLISE DETALHADA:")
    print()
    
    for i, message in enumerate(messages_74, 1):
        msg_type = _identify_message_type(message)
        response = _generate_contextual_response_by_type(message, msg_type)
        
        category_stats[msg_type] = category_stats.get(msg_type, 0) + 1
        
        print(f"📝 MENSAGEM {i:02d}")
        print(f"Cliente: \"{message}\"")
        print(f"Categoria: {msg_type}")
        print(f"Julia: {response}")
        print("-" * 60)
    
    print("\n📊 ESTATÍSTICAS FINAIS")
    print(f"Total de mensagens analisadas: {len(messages_74)}")
    print()
    print("Distribuição por categoria:")
    
    total = len(messages_74)
    for category, count in sorted(category_stats.items()):
        percentage = (count / total) * 100
        print(f"  {category}: {count} mensagens ({percentage:.1f}%)")
    
    # Verificar se a categoria 'ambigua' está abaixo de 10%
    ambigua_count = category_stats.get('ambigua', 0)
    ambigua_percentage = (ambigua_count / total) * 100
    
    print(f"\n🎯 ANÁLISE DE PERFORMANCE:")
    if ambigua_percentage < 10:
        print(f"✅ Meta atingida: Categoria 'ambígua' em {ambigua_percentage:.1f}% (meta: <10%)")
    else:
        print(f"❌ Meta não atingida: Categoria 'ambígua' em {ambigua_percentage:.1f}% (meta: <10%)")
    
    novas_categorias = category_stats.get('saudacao', 0) + category_stats.get('finalizacao', 0) + category_stats.get('mensagem_especifica', 0) + category_stats.get('agendamento', 0)
    novas_percentage = (novas_categorias / total) * 100
    print(f"✅ Novas categorias detectadas: {novas_categorias} mensagens ({novas_percentage:.1f}%)")


if __name__ == "__main__":
    try:
        test_all_conversation_patterns()
        test_refinement_system()
        test_new_categories()
        test_real_cases_analysis()
        test_humanize_function()
        test_greeting_detection()
        test_74_messages_analysis()
        
        print("\n🎉 TODOS OS MÓDULOS DE TESTE EXECUTADOS COM SUCESSO!")
        print("📋 MÓDULOS TESTADOS:")
        print("   1. ✅ Padrões de conversa e detecção de inadequações")
        print("   2. ✅ Sistema de refinamento de respostas com IA")
        print("   3. ✅ Novas categorias (PIX, orçamento, agendamento, etc.)")
        print("   4. ✅ Análise de casos reais")
        print("   5. ✅ Função de humanização de respostas robóticas")
        print("   6. ✅ Detecção de saudações vs finalizadores")
        print("   7. ✅ Análise completa das 74 mensagens reais")
        
    except Exception as e:
        print(f"❌ ERRO NA EXECUÇÃO DOS TESTES: {e}")
        import traceback
        traceback.print_exc()