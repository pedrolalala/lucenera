import os
import sys
sys.path.insert(0, os.getcwd())

def test_technical_content_detection():
    # Mensagem da Marina com saudação + conteúdo técnico
    marina_msg = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final"
    
    # Mensagem apenas de saudação
    greeting_only = "Boa tarde! Tudo bem?"
    
    # Mensagem técnica sem saudação
    technical_only = "A profundidade que você perguntou: O PD acabado vou te mandar a planta de forro final"
    
    print("=== TESTE DETECÇÃO DE CONTEÚDO TÉCNICO ===")
    
    for msg, label in [(marina_msg, "Marina (saudação + técnico)"), (greeting_only, "Saudação pura"), (technical_only, "Técnico puro")]:
        print(f"\n{label}:")
        print(f"Mensagem: '{msg}'")
        
        # Simular a nova lógica
        txt_lower = msg.lower()
        technical_keywords = [
            # Projeto/construção
            "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
            "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
            # Estoque/materiais  
            "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
            # Técnicas específicas
            "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
            # Preços/prazos
            "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando",
            # Perguntas técnicas
            "como", "onde", "qual", "quando", "consegue", "pode", "tem", "instalar"
        ]
        
        has_technical_content = any(keyword in txt_lower for keyword in technical_keywords)
        found_keywords = [k for k in technical_keywords if k in txt_lower]
        
        print(f"  Conteúdo técnico: {has_technical_content}")
        if found_keywords:
            print(f"  Keywords encontrados: {found_keywords}")
        
        # Simular is_greeting
        import re
        GREETINGS_RE = re.compile(
            r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))',
            re.I
        )
        is_greeting = GREETINGS_RE.match(msg.strip()) is not None
        
        # Nova lógica smalltalk
        smalltalk = is_greeting and (not has_technical_content)
        
        print(f"  É greeting: {is_greeting}")
        print(f"  Será smalltalk: {smalltalk}")
        
        if smalltalk:
            print("  🎯 Resultado: SMALLTALK (resposta de saudação)")
        else:
            print("  🎯 Resultado: VAI PARA IA (processar conteúdo completo)")

if __name__ == "__main__":
    test_technical_content_detection()