import os
import sys
sys.path.insert(0, os.getcwd())

def test_henry_greeting_detection():
    # Importar as funções necessárias
    try:
        from main import is_finalizing_message
        print("✅ is_finalizing_message importado")
        
        # Encontrar _safe_is_greeting no código
        import inspect
        import main
        
        # Buscar função _safe_is_greeting
        for name, obj in inspect.getmembers(main):
            if name == '_safe_is_greeting' and callable(obj):
                _safe_is_greeting = obj
                print("✅ _safe_is_greeting encontrado")
                break
        else:
            print("❌ _safe_is_greeting não encontrado")
            return
            
        # Testar a mensagem do Henry
        msg = "Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton"
        
        print(f"\n=== TESTE HENRY - DETECÇÃO COMPLETA ===")
        print(f"Mensagem: '{msg}'")
        print(f"  _safe_is_greeting: {_safe_is_greeting(msg)}")
        print(f"  is_finalizing_message: {is_finalizing_message(msg)}")
        
        # Testar a lógica exata do smalltalk
        is_greeting = _safe_is_greeting(msg)
        is_finalizer = is_finalizing_message(msg)
        smalltalk_condition = is_greeting and (not is_finalizer)
        
        print(f"\n=== LÓGICA SMALLTALK ===")
        print(f"  is_greeting: {is_greeting}")
        print(f"  is_finalizer: {is_finalizer}")
        print(f"  smalltalk = is_greeting AND (NOT is_finalizer): {smalltalk_condition}")
        
        if smalltalk_condition:
            print("\n🚨 PROBLEMA: Mensagem será processada como SMALLTALK, não como FINALIZER!")
        else:
            print("\n✅ OK: Mensagem chegará na verificação de finalizer")
            
    except ImportError as e:
        print(f"Erro ao importar: {e}")

if __name__ == "__main__":
    test_henry_greeting_detection()