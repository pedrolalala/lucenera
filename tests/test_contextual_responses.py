# -*- coding: utf-8 -*-
"""
Teste para verificar se o novo sistema de respostas contextuais funciona corretamente.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import _humanize_robotic_response

def test_contextual_responses():
    """Testa se as perguntas especificas geram respostas diretas e relevantes."""
    
    test_cases = [
        # PROBLEMA ORIGINAL - perguntas QUANDO
        {
            "original": "Quando foi enviado essa oferta?",
            "robotic": "Recebi sua mensagem",
            "expected_contains": ["data", "envio"],
            "should_not_contain": ["valores", "prazos"],
            "description": "Pergunta QUANDO sobre envio (caso original)"
        },
        {
            "original": "Quando chega a entrega?",
            "robotic": "Entendi",
            "expected_contains": ["entrega", "previsao"],
            "should_not_contain": ["valores", "precos"],
            "description": "Pergunta QUANDO sobre entrega"
        },
        
        # Perguntas QUANTO
        {
            "original": "Quanto custa a luminaria?",
            "robotic": "Compreendo",
            "expected_contains": ["valores", "orcamento"],
            "should_not_contain": ["data", "entrega"],
            "description": "Pergunta QUANTO sobre preco"
        },
        
        # Perguntas COMO
        {
            "original": "Como instala essa luminaria?",
            "robotic": "Recebi",
            "expected_contains": ["instalacao", "processo"],
            "should_not_contain": ["valores", "precos"],
            "description": "Pergunta COMO sobre processo"
        },
        
        # Perguntas ONDE
        {
            "original": "Onde fica localizada a empresa?",
            "robotic": "Entendi",
            "expected_contains": ["localizacao"],
            "should_not_contain": ["valores", "instalacao"],
            "description": "Pergunta ONDE sobre localizacao"
        },
        
        # Perguntas QUAL
        {
            "original": "Qual modelo voce recomenda?",
            "robotic": "Compreendo",
            "expected_contains": ["modelos", "opcoes"],
            "should_not_contain": ["data", "entrega"],
            "description": "Pergunta QUAL sobre especificacao"
        },
        
        # Perguntas TEM/HA
        {
            "original": "Tem disponivel no estoque?",
            "robotic": "Recebi",
            "expected_contains": ["disponibilidade", "estoque"],
            "should_not_contain": ["data", "valores"],
            "description": "Pergunta TEM sobre disponibilidade"
        },
        
        # Verificar se mantem saudacao
        {
            "original": "Quando foi enviado essa oferta?",
            "robotic": "Recebi sua mensagem",
            "expected_contains": ["dia", "tarde", "noite"],  # Alguma saudacao
            "should_not_contain": [],
            "description": "Verificar se inclui saudacao apropriada"
        }
    ]
    
    print("Testando novo sistema de respostas contextuais...\n")
    
    total_tests = len(test_cases)
    passed = 0
    
    for i, case in enumerate(test_cases, 1):
        original = case["original"]
        robotic = case["robotic"]
        expected = case["expected_contains"]
        should_not = case["should_not_contain"]
        desc = case["description"]
        
        result = _humanize_robotic_response(robotic, "Cliente", original)
        result_lower = result.lower()
        
        # Verificar se contem palavras esperadas
        has_expected = len(expected) == 0 or any(word.lower() in result_lower for word in expected)
        
        # Verificar se NAO contem palavras que nao deveria
        has_unwanted = any(word.lower() in result_lower for word in should_not)
        
        test_passed = has_expected and not has_unwanted
        status = "PASS" if test_passed else "FAIL"
        
        print(f"  {i:2d}. {status} {desc}")
        print(f"      Pergunta: '{original}'")
        print(f"      Resposta: '{result}'")
        print(f"      Deve conter: {expected if expected else '(qualquer saudacao)'}")
        if should_not:
            print(f"      NAO deve conter: {should_not}")
        
        if test_passed:
            passed += 1
        else:
            print(f"      FALHA!")
            if not has_expected and expected:
                print(f"         - Faltam palavras esperadas: {expected}")
            if has_unwanted:
                print(f"         - Contem palavras indesejadas: {should_not}")
        print()
    
    print(f"Resultado: {passed}/{total_tests} testes passaram")
    
    if passed == total_tests:
        print("SUCESSO! Sistema de respostas contextuais funcionando perfeitamente!")
        print("Agora responde DIRETAMENTE o que foi perguntado")
        print("Tom profissional e consultivo")
        print("Saudacoes apropriadas incluidas")
    elif passed >= total_tests * 0.8:
        print("BOM PROGRESSO! Maioria das respostas melhorada significativamente")
    else:
        print("PRECISA MAIS AJUSTES - verificar logica de deteccao")
    
    return passed == total_tests

if __name__ == "__main__":
    test_contextual_responses()