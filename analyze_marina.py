import os
import sys
sys.path.insert(0, os.getcwd())

from main import is_finalizing_message

def analyze_marina_message():
    # Mensagem exata da Marina
    msg = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final"
    
    print("=== ANÁLISE MENSAGEM MARINA ===")
    print(f"Mensagem: '{msg}'")
    print()
    
    # Teste 1: Finalizer
    is_finalizer = is_finalizing_message(msg)
    print(f"is_finalizing_message: {is_finalizer}")
    
    # Teste 2: GREETINGS_RE
    import re
    GREETINGS_RE = re.compile(
        r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))',
        re.I
    )
    
    greeting_match = GREETINGS_RE.match(msg.strip())
    print(f"GREETINGS_RE.match: {greeting_match is not None}")
    if greeting_match:
        print(f"  Grupo capturado: '{greeting_match.group()}'")
    
    # Teste 3: Detectar se seria smalltalk
    msg_lower = msg.lower()
    
    # Simular _safe_is_greeting (seria True por causa do "Boa tarde")
    is_greeting_detected = greeting_match is not None
    print(f"Detectado como greeting: {is_greeting_detected}")
    
    # Verificar se tem conteúdo técnico
    technical_words = ["profundidade", "pd", "projeto", "planta", "forro", "acabado", "final"]
    found_technical = [w for w in technical_words if w in msg_lower]
    print(f"Palavras técnicas encontradas: {found_technical}")
    
    # Verificar tamanho da mensagem
    print(f"Tamanho da mensagem: {len(msg)} caracteres")
    
    print()
    print("=== DIAGNÓSTICO ===")
    if is_greeting_detected:
        print("🚨 PROBLEMA: Mensagem detectada como GREETING")
        if len(msg) > 30 and found_technical:
            print("❌ MAS tem conteúdo técnico e é longa - NÃO deveria ser tratada como saudação pura")
            print("🎯 CAUSA: Lógica de humanização pode estar priorizando a saudação")
        else:
            print("✅ Seria correto tratar como saudação")
    
    # Verificar se passaria pelos filtros de humanização
    print("\n=== VERIFICAÇÃO HUMANIZAÇÃO ===")
    
    # Padrões de projeto
    projeto_patterns = [
        "projeto", "luminária", "luminaria", "ponto", "acrescentar", "iluminação", "iluminacao",
        "beiral", "gesso", "traçado", "layout", "porro", "garagem", "manter assim", "confirmar"
    ]
    projeto_match = [p for p in projeto_patterns if p in msg_lower]
    print(f"Projeto patterns: {projeto_match}")
    
    # A palavra "projeto" não está, mas "planta" e "forro" são técnicas
    if not projeto_match and found_technical:
        print("🚨 PROBLEMA: Palavras técnicas importantes não estão nos padrões!")
        print(f"   Palavras técnicas não mapeadas: {found_technical}")

if __name__ == "__main__":
    analyze_marina_message()