#!/usr/bin/env python3
"""
Teste para verificar se "isso" é detectado como finalizer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import is_finalizing_message

def test_finalizer_detection():
    """Testa se 'isso' e variações são detectadas como finalizers."""
    
    test_cases = [
        # Casos que DEVEM ser detectados como finalizer
        ("isso", True),
        ("Isso", True), 
        ("isso mesmo", True),
        ("exatamente", True),
        ("ok", True),
        ("sim", True),
        ("certo", True),
        ("👍", True),
        
        # Casos que NÃO devem ser detectados como finalizer
        ("isso que eu queria saber", False),
        ("isso é um problema", False),
        ("como isso funciona?", False),
        ("preciso disso hoje", False),
        
        # Casos específicos do contexto
        ("Quando vocês atualizarem, me manda pra eu mandar pra Automundi?", False),
        ("Pergunto caso queiram encaminhar alguma outra referencia", False),
        ("Isso, a questão seria o rasgo aberto ou acrílico", False),  # Tem elaboração
    ]
    
    print("🧪 Testando detecção de finalizers...\n")
    
    total_tests = len(test_cases)
    passed = 0
    
    for i, (text, expected) in enumerate(test_cases, 1):
        result = is_finalizing_message(text)
        status = "✅" if result == expected else "❌"
        
        print(f"  {i:2d}. {status} '{text[:50]}{'...' if len(text) > 50 else ''}'")
        print(f"      Esperado: {expected}, Resultado: {result}")
        
        if result == expected:
            passed += 1
        else:
            print(f"      ⚠️ FALHA!")
        print()
    
    print(f"📊 Resultado: {passed}/{total_tests} testes passaram")
    
    if passed == total_tests:
        print("🎉 Todos os testes passaram! 'Isso' agora é detectado como finalizer.")
    else:
        print("❌ Alguns testes falharam - verificar lógica de detecção")
    
    return passed == total_tests

if __name__ == "__main__":
    test_finalizer_detection()