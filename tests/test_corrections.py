#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste das correcoes implementadas:
1. Remocao de saudacoes desnecessarias 
2. Respostas adequadas para agradecimentos
"""

from main import _generate_contextual_response_by_type, _generate_finalization_response

def test_corrections():
    print("TESTANDO CORRECOES IMPLEMENTADAS")
    print("=" * 50)
    
    # Teste 1: Saudacoes desnecessarias removidas
    print("\n1. TESTE: Remocao de saudacoes desnecessarias")
    print("-" * 45)
    
    test_msg1 = "Preciso tbm achar um pendente pra mesa de jantar dele!!"
    response1 = _generate_contextual_response_by_type(test_msg1, 'mensagem_especifica')
    print(f"Mensagem: '{test_msg1}'")
    print(f"Resposta: '{response1}'")
    
    # Verificar se nao tem saudacao desnecessaria
    has_greeting = any(greeting in response1.lower() for greeting in ["bom dia", "boa tarde", "boa noite"])
    if not has_greeting:
        print("SUCESSO: Resposta sem saudacao desnecessaria!")
    else:
        print("PROBLEMA: Resposta ainda tem saudacao desnecessaria!")
    
    # Teste 2: Agradecimentos adequados
    print("\n2. TESTE: Respostas adequadas para agradecimentos")
    print("-" * 45)
    
    test_msg2 = "Obrigado por enviar os orcamentos e pela explicacao."
    response2 = _generate_finalization_response(test_msg2, "")
    print(f"Mensagem: '{test_msg2}'")
    print(f"Resposta: '{response2}'")
    
    # Verificar se nao menciona financeiro inadequadamente
    has_financeiro = any(word in response2.lower() for word in ["financeiro", "alinhar", "te aviso"])
    if not has_financeiro:
        print("SUCESSO: Resposta adequada para agradecimento!")
    else:
        print("PROBLEMA: Resposta ainda menciona financeiro inadequadamente!")
    
    # Teste 3: Verificar outras respostas contextuais
    print("\n3. TESTE: Outras respostas sem saudacao")
    print("-" * 45)
    
    test_msg3 = "Quanto custa uma luminaria pendente?"
    response3 = _generate_contextual_response_by_type(test_msg3, 'mensagem_especifica')
    print(f"Mensagem: '{test_msg3}'")
    print(f"Resposta: '{response3}'")
    
    has_greeting3 = any(greeting in response3.lower() for greeting in ["bom dia", "boa tarde", "boa noite"])
    if not has_greeting3:
        print("SUCESSO: Resposta direta sem saudacao!")
    else:
        print("PROBLEMA: Ainda adiciona saudacao desnecessaria!")
    
    print("\n" + "=" * 50)
    print("TESTES DE CORRECAO CONCLUIDOS!")

if __name__ == "__main__":
    test_corrections()