#!/usr/bin/env python3
"""
Teste para verificar se perguntas sobre entrega são detectadas corretamente.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import _humanize_robotic_response

def test_entrega_detection():
    """Testa se perguntas sobre entrega têm respostas específicas."""
    
    test_cases = [
        # Casos de entrega que devem ter respostas específicas
        {
            "original": "Confirmada a entrega do material hoje?",
            "robotic_response": "Recebi sua mensagem",
            "expected_contains": ["confirmação", "entrega"],
            "should_not_contain": ["valores", "prazos"],
            "description": "Confirmação de entrega (caso Bruno Cisotto)"
        },
        {
            "original": "Quando chega o material?",
            "robotic_response": "Entendi sua mensagem",
            "expected_contains": ["entrega", "material"],
            "should_not_contain": ["valores", "prazos"],
            "description": "Pergunta sobre entrega simples"
        },
        {
            "original": "O material já foi entregue?",
            "robotic_response": "Compreendo",
            "expected_contains": ["entrega", "material"],
            "should_not_contain": ["valores", "prazos"],
            "description": "Status de entrega"
        },
        {
            "original": "Chegou a luminária que pedi?",
            "robotic_response": "Recebi sua mensagem",
            "expected_contains": ["entrega", "material"],
            "should_not_contain": ["valores", "prazos"],
            "description": "Material específico chegou"
        },
        # Casos que DEVEM continuar sendo preços/prazos
        {
            "original": "Qual o preço da luminária?",
            "robotic_response": "Entendi",
            "expected_contains": ["valores", "prazos"],
            "should_not_contain": ["entrega"],
            "description": "Pergunta sobre preço (deve manter preço/prazo)"
        },
        {
            "original": "Quanto tempo demora para fabricar?",
            "robotic_response": "Compreendo",
            "expected_contains": ["valores", "prazos"],
            "should_not_contain": ["entrega"],
            "description": "Pergunta sobre prazo de fabricação"
        }
    ]
    
    print("🧪 Testando detecção específica de entrega vs preços/prazos...\n")
    
    total_tests = len(test_cases)
    passed = 0
    
    for i, case in enumerate(test_cases, 1):
        original = case["original"]
        robotic = case["robotic_response"]
        expected = case["expected_contains"]
        should_not = case["should_not_contain"]
        desc = case["description"]
        
        result = _humanize_robotic_response(robotic, "Cliente", original)
        result_lower = result.lower()
        
        # Verificar se contém palavras esperadas
        has_expected = any(word.lower() in result_lower for word in expected)
        
        # Verificar se NÃO contém palavras que não deveria
        has_unwanted = any(word.lower() in result_lower for word in should_not)
        
        test_passed = has_expected and not has_unwanted
        status = "✅" if test_passed else "❌"
        
        print(f"  {i:2d}. {status} {desc}")
        print(f"      📩 Original: '{original}'")
        print(f"      🤖 Resposta: '{result}'")
        print(f"      ✓ Deve conter: {expected}")
        print(f"      ✗ NÃO deve conter: {should_not}")
        
        if test_passed:
            passed += 1
        else:
            print(f"      ⚠️ FALHA!")
            if not has_expected:
                print(f"         - Faltam palavras esperadas: {expected}")
            if has_unwanted:
                print(f"         - Contém palavras indesejadas: {should_not}")
        print()
    
    print(f"📊 Resultado: {passed}/{total_tests} testes passaram")
    
    if passed == total_tests:
        print("🎉 Todos os testes passaram! Entregas e preços agora são detectados corretamente.")
    else:
        print("❌ Alguns testes falharam - verificar lógica de detecção")
    
    return passed == total_tests

if __name__ == "__main__":
    test_entrega_detection()