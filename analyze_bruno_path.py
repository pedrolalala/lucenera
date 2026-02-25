import os
import sys
sys.path.insert(0, os.getcwd())

from main import is_finalizing_message

def analyze_bruno_message():
    # Mensagem exata do Bruno
    msg1 = "Marquei com o Leo para ir na segunda instalar"
    msg2 = "COnsegue os perfis e o desenho para amanhã??"
    combined = f"{msg1} {msg2}"  # Como seria após debounce
    
    print("=== ANÁLISE MENSAGEM BRUNO CISOTTO ===")
    print(f"Msg 1: '{msg1}'")
    print(f"Msg 2: '{msg2}'") 
    print(f"Combined: '{combined}'")
    print()
    
    print("=== VERIFICAÇÕES DE DETECÇÃO ===")
    
    # Teste 1: Finalizer
    print(f"is_finalizing_message(msg1): {is_finalizing_message(msg1)}")
    print(f"is_finalizing_message(msg2): {is_finalizing_message(msg2)}")
    print(f"is_finalizing_message(combined): {is_finalizing_message(combined)}")
    print()
    
    # Teste 2: GREETINGS_RE
    import re
    GREETINGS_RE = re.compile(
        r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))',
        re.I
    )
    
    print("=== TESTE GREETING ===")
    for msg, label in [(msg1, "msg1"), (msg2, "msg2"), (combined, "combined")]:
        match = GREETINGS_RE.match(msg.strip())
        print(f"GREETINGS_RE.match({label}): {match is not None}")
    print()
    
    # Teste 3: _needs_clarify - vou simular os padrões mais comuns
    CLARIFY_KEYWORDS = ["quando", "onde", "como", "qual", "que horas", "quanto", "pode", "consegue", "tem"]
    
    print("=== TESTE CLARIFY INDICATORS ===")
    for msg, label in [(msg1, "msg1"), (msg2, "msg2"), (combined, "combined")]:
        has_clarify = any(keyword in msg.lower() for keyword in CLARIFY_KEYWORDS)
        print(f"Possível clarify em {label}: {has_clarify}")
        if has_clarify:
            found_keywords = [k for k in CLARIFY_KEYWORDS if k in msg.lower()]
            print(f"  Keywords encontrados: {found_keywords}")
    print()
    
    # Conclusão do caminho
    is_finalizer = is_finalizing_message(combined)
    is_greeting = GREETINGS_RE.match(combined.strip()) is not None
    has_question = "?" in combined
    
    print("=== CONCLUSÃO DO CAMINHO ===")
    print(f"✅ is_finalizer: {is_finalizer}")
    print(f"✅ is_greeting: {is_greeting}")  
    print(f"✅ has_question: {has_question}")
    print(f"✅ Mensagem contém pergunta técnica: {'perfis' in combined and 'desenho' in combined}")
    
    if not is_finalizer and not is_greeting and has_question:
        print("\n🎯 CAMINHO PROVÁVEL:")
        print("1. ❌ NÃO é finalizer")
        print("2. ❌ NÃO é pure_greeting") 
        print("3. ❌ NÃO é smalltalk")
        print("4. ✅ Vai para fluxo normal de AI")
        print("5. 🚨 Provavelmente caiu no FALLBACK GENÉRICO")
        print("6. 📝 Gerou resposta: 'Vou verificar e te retorno com as informações'")

if __name__ == "__main__":
    analyze_bruno_message()