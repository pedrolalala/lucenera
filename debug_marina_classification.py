"""
Debug detalhado para identificar onde a mensagem da Marina está sendo mal classificada
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def debug_marina_classification():
    """Debug step-by-step da classificação da Marina"""
    
    # Mensagem da Marina
    txt = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final"
    
    print("=== DEBUG CLASSIFICAÇÃO MARINA ===")
    print(f"Mensagem: '{txt}'")
    print()
    
    from main import is_finalizing_message
    import re
    
    # 1. VERIFICAÇÃO FINALIZER
    is_finalizer = is_finalizing_message(txt)
    print(f"🏁 is_finalizing_message: {is_finalizer}")
    
    # 2. VERIFICAÇÃO GREETING
    GREETINGS_RE = re.compile(r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))', re.I)
    is_greeting = GREETINGS_RE.match(txt.strip()) is not None
    print(f"👋 is_greeting: {is_greeting}")
    
    # 3. VERIFICAÇÃO CONTEÚDO TÉCNICO (nossa correção)
    txt_lower = txt.lower()
    technical_keywords = [
        "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
        "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
        "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
        "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
        "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando", "instalar",
        "como", "onde", "qual", "consegue", "pode", "tem", "técnico", "entregar"
    ]
    has_technical_content = any(keyword in txt_lower for keyword in technical_keywords)
    technical_found = [k for k in technical_keywords if k in txt_lower]
    
    print(f"🔧 has_technical_content: {has_technical_content}")
    print(f"📝 technical_found: {technical_found}")
    
    # 4. NOVA LÓGICA SMALLTALK (nossa correção)
    print(f"\n=== NOVA LÓGICA SMALLTALK ===")
    try:
        # Simular _safe_is_greeting - ele usa GREETINGS_RE
        is_greeting_only = is_greeting  # simplificado
        smalltalk = is_greeting_only and (not is_finalizer) and (not has_technical_content)
        print(f"is_greeting_only: {is_greeting_only}")
        print(f"not is_finalizer: {not is_finalizer}")
        print(f"not has_technical_content: {not has_technical_content}")
        print(f"RESULTADO smalltalk: {smalltalk}")
    except Exception as e:
        print(f"Erro: {e}")
        smalltalk = False
    
    # 5. VERIFICAR SE A CORREÇÃO ESTÁ NO CÓDIGO
    print(f"\n=== VERIFICANDO SE A CORREÇÃO ESTÁ APLICADA ===")
    
    # Ler o código atual da função para ver se nossa correção está lá
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Procurar nossa correção
        if "has_technical_content = any(keyword in txt_lower for keyword in technical_keywords)" in content:
            print("✅ Correção de conteúdo técnico ESTÁ no código")
        else:
            print("❌ Correção de conteúdo técnico NÃO está no código!")
            
        if "smalltalk = is_greeting_only and (not is_finalizer) and (not has_technical_content)" in content:
            print("✅ Nova lógica de smalltalk ESTÁ no código")
        else:
            print("❌ Nova lógica de smalltalk NÃO está no código!")
            
    except Exception as e:
        print(f"Erro ao ler arquivo: {e}")
    
    # 6. RESULTADO FINAL
    print(f"\n=== RESULTADO ESPERADO ===")
    if smalltalk:
        print("🚨 PROBLEMA: Ainda será tratado como SMALLTALK")
        print("   Vai gerar resposta de saudação")
    else:
        print("✅ CORRETO: VAI PARA IA processar conteúdo técnico")
        print("   Deveria gerar resposta sobre projeto")

if __name__ == "__main__":
    debug_marina_classification()