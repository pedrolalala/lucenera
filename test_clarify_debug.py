import os
import sys
sys.path.insert(0, os.getcwd())

from main import _needs_clarify

def test_henry_clarify():
    # Testar as mensagens do Henry
    msgs = [
        "Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton",
        "Obrigado",
        "Bom dia Murilo tudo bem ?",  # só a parte saudação
        "Entendi vou repassar para o Airton"  # só a parte finalizer
    ]
    
    print("=== TESTE _needs_clarify - HENRY ===")
    for msg in msgs:
        clarify = _needs_clarify(msg)
        is_pure_greeting = (clarify == "__pure_greeting__")
        print(f"'{msg}'")
        print(f"  _needs_clarify: {clarify}")
        print(f"  is_pure_greeting: {is_pure_greeting}")
        print()

if __name__ == "__main__":
    test_henry_clarify()