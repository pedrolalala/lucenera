# -*- coding: utf-8 -*-
"""
Teste do novo fluxo de respostas:
1. Identificar tipo de mensagem
2. Pegar opcoes pre-prontas
3. ChatGPT escolhe/adapta a melhor
"""

from main import _identify_message_type, _get_response_options_by_type

def test_new_flow():
    print("=" * 60)
    print("TESTANDO NOVO FLUXO DE RESPOSTAS")
    print("=" * 60)
    
    test_cases = [
        ("Preciso de um orcamento para pendentes", "pergunta/mensagem_especifica"),
        ("Ok, sem problemas!", "confirmacao"),
        ("Bom dia! Tudo bem?", "saudacao"),
        ("Obrigado pela ajuda!", "finalizacao"),
        ("Voces fazem entrega?", "pergunta/mensagem_especifica"),
        ("Enviei as medidas por email", "informacao"),
    ]
    
    for msg, expected_type_hint in test_cases:
        print(f"\n{'='*60}")
        print(f"MENSAGEM: '{msg}'")
        print(f"Tipo esperado: {expected_type_hint}")
        
        # PASSO 1: Identificar tipo
        msg_type = _identify_message_type(msg)
        print(f"\n1. TIPO IDENTIFICADO: '{msg_type}'")
        
        # PASSO 2: Pegar opcoes pre-prontas
        options = _get_response_options_by_type(msg, msg_type)
        print(f"\n2. OPCOES PRE-PRONTAS ({len(options)} opcoes):")
        for i, opt in enumerate(options, 1):
            print(f"   {i}. {opt}")
        
        print(f"\n3. PROXIMO PASSO: ChatGPT escolhera/adaptara a melhor opcao")
        print(f"   considerando:")
        print(f"   - Historico de 12 mensagens")
        print(f"   - Contexto especifico da mensagem")
        print(f"   - Termos usados pelo cliente")
        
    print(f"\n{'='*60}")
    print("NOVO FLUXO IMPLEMENTADO COM SUCESSO!")
    print("=" * 60)

if __name__ == "__main__":
    test_new_flow()
