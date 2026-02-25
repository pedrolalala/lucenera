"""
Verificar se _needs_clarify está interceptando a mensagem da Marina
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def check_needs_clarify():
    """Verificar se _needs_clarify está causando o problema"""
    
    # Mensagem da Marina
    txt = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final"
    
    print("=== VERIFICAR _needs_clarify() ===")
    print(f"Mensagem: '{txt}'")
    print()
    
    from main import _needs_clarify
    
    # Verificar o que _needs_clarify retorna
    clarify = _needs_clarify(txt)
    
    print(f"🔍 _needs_clarify() retorna: {clarify}")
    
    if clarify == "__pure_greeting__":
        print("🚨 PROBLEMA ENCONTRADO: _needs_clarify classifica como __pure_greeting__")
        print("   Isso faz a mensagem ir para o fluxo de saudação pura!")
    elif clarify == "__ignore_greeting__":
        print("✅ _needs_clarify retorna __ignore_greeting__ (não é problema)")
    elif clarify is None:
        print("✅ _needs_clarify retorna None (não intercepta)")
    else:
        print(f"❓ _needs_clarify retorna clarify específico: '{clarify}'")
        
    # Verificar as condições
    is_pure_greeting = (clarify == "__pure_greeting__")
    needs_clarify = bool(clarify and clarify not in {"__ignore_greeting__", "__pure_greeting__"})
    
    print()
    print(f"📊 RESULTADO:")
    print(f"   is_pure_greeting: {is_pure_greeting}")
    print(f"   needs_clarify: {needs_clarify}")
    
    if is_pure_greeting:
        print("\n🚨 AQUI ESTÁ O PROBLEMA!")
        print("   A mensagem vai ser tratada como saudação pura")
        print("   E vai chamar _gentle_greeting_reply() em vez da IA!")

if __name__ == "__main__":
    check_needs_clarify()