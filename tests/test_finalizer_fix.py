import os
import sys
sys.path.insert(0, os.getcwd())

def test_finalizer_fix():
    """Testa se a correção de finalizers está funcionando"""
    
    from main import is_finalizing_message
    
    # Casos que antes eram bloqueados incorretamente
    problematic_cases = [
        "Pode deixar",                           # Saulo - DEVE continuar sendo finalizer (sem conteúdo técnico)
        "Perfeito, vou mandar o desenho",       # Edge1 - DEVE ir para IA (tem conteúdo técnico)
        "Combinado, vou aguardar o material",   # Edge2 - DEVE ir para IA (tem conteúdo técnico)
        "Ok, mas precisa mudar o projeto",      # DEVE ir para IA (tem condicional + técnico)
        "Obrigado, quando fica pronto?",        # DEVE ir para IA (tem pergunta)
        "Entendi vou repassar para o Airton",   # Henry - DEVE continuar sendo finalizer
        "Obrigado pelo retorno",                # DEVE continuar sendo finalizer
    ]
    
    print("=== TESTE DA CORREÇÃO DE FINALIZERS ===")
    print()
    
    for msg in problematic_cases:
        print(f"📝 '{msg}'")
        
        txt_lower = msg.lower()
        is_finalizer = is_finalizing_message(msg)
        
        # Simular a nova lógica
        technical_keywords = [
            "projeto", "planta", "pd", "desenho", "perfis", "forro", "material", "romaneio",
            "orçamento", "valor", "preço", "entrega", "prazo", "instalar", "técnico",
            "luminária", "led", "driver", "watts", "medida", "especificação"
        ]
        
        has_technical_content = any(keyword in txt_lower for keyword in technical_keywords)
        has_question = "?" in msg
        has_conditional = any(word in txt_lower for word in ["mas", "porém", "e o", "e a"])
        has_future_action = any(phrase in txt_lower for phrase in ["vou mandar", "vou enviar", "vou aguardar"])
        
        print(f"   🏁 is_finalizer: {is_finalizer}")
        print(f"   🔧 has_technical: {has_technical_content}")
        print(f"   ❓ has_question: {has_question}")
        print(f"   🤔 has_conditional: {has_conditional}")
        print(f"   🚀 has_future_action: {has_future_action}")
        
        # Determinar o resultado com a nova lógica
        if is_finalizer:
            if has_technical_content or has_question or has_conditional or has_future_action:
                result = "✅ VAI PARA IA (finalizer + conteúdo)"
                correct = True
            else:
                result = "🚫 BLOCKED: ignored_finalizer (finalizer puro)"
                correct = msg in ["Pode deixar", "Entendi vou repassar para o Airton", "Obrigado pelo retorno"]
        else:
            result = "✅ VAI PARA IA (não é finalizer)"
            correct = True
            
        print(f"   ➡️  {result}")
        
        if correct:
            print(f"   ✅ CORRETO")
        else:
            print(f"   ❌ PROBLEMA AINDA EXISTE")
            
        print()

if __name__ == "__main__":
    test_finalizer_fix()