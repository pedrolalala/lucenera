import os
import sys
sys.path.insert(0, os.getcwd())

from main import is_finalizing_message

def test_henry_case():
    # Simular o caso Henry: duas mensagens em sequência
    msgs = [
        "Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton",
        "Obrigado"
    ]
    
    print("=== TESTE HENRY - MENSAGENS INDIVIDUAIS ===")
    for i, msg in enumerate(msgs, 1):
        print(f"\nMensagem {i}: '{msg}'")
        print(f"  is_finalizing_message: {is_finalizing_message(msg)}")
    
    # Testar mensagem combinada (como seria no debounce)
    combined = " ".join(msgs)
    print(f"\n=== MENSAGEM COMBINADA (DEBOUNCE) ===")
    print(f"Texto: '{combined}'")
    print(f"  is_finalizing_message: {is_finalizing_message(combined)}")
    
    # Testar apenas a parte "Entendi vou repassar para o Airton"
    parte_chave = "Entendi vou repassar para o Airton"
    print(f"\n=== APENAS PARTE CHAVE ===")
    print(f"Texto: '{parte_chave}'")
    print(f"  is_finalizing_message: {is_finalizing_message(parte_chave)}")

if __name__ == "__main__":
    test_henry_case()