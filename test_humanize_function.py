"""
Testar especificamente a função _humanize_robotic_response
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_humanize_function():
    """Testa diretamente a função de humanização"""
    
    from main import _humanize_robotic_response
    
    # Mensagem da Marina
    original_msg = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final"
    
    # Respostas que o ChatGPT gerou (inadequadas)
    test_cases = [
        ("Marina v1", "**Julia:** Tudo otimo, obrigada por perguntar, e com você?"),
        ("Marina v2", "**Julia:** Boa tarde, tudo otimo e com você?"),
    ]
    
    print("=== TESTE FUNÇÃO _humanize_robotic_response ===")
    print(f"Mensagem original: '{original_msg}'")
    print()
    
    for name, chatgpt_response in test_cases:
        print(f"📋 {name}")
        print(f"ChatGPT disse: '{chatgpt_response}'")
        
        # Aplicar humanização
        final_response = _humanize_robotic_response(chatgpt_response, "Marina", original_msg)
        
        print(f"APÓS humanização: '{final_response}'")
        
        if final_response != chatgpt_response:
            print(f"✅ CORREÇÃO APLICADA!")
        else:
            print(f"❌ Resposta não foi corrigida")
            
        print("=" * 70)
        print()

if __name__ == "__main__":
    test_humanize_function()