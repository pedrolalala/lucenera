import os
import sys
sys.path.insert(0, os.getcwd())

def analyze_all_flow_interceptors():
    """Analisa todos os pontos onde uma mensagem pode ser interceptada antes da IA"""
    
    print("=== ANÁLISE COMPLETA DOS INTERCEPTADORES DE FLUXO ===")
    print()
    
    # Mensagens de teste que representam casos reais
    test_messages = [
        "Boa tarde! Consegue os perfis para amanhã?",  # Greeting + técnico
        "Obrigado pelo retorno",                       # Possível finalizer
        "Tudo bem por aí?",                           # Greeting puro
        "Quando fica pronto o projeto?",              # Pergunta direta
        "Oi, pode me mandar o orçamento?",           # Greeting + pedido
        "Entendi, vou aguardar",                      # Finalizer + conteúdo
        "Ok, então fica assim mesmo",                 # Finalizer complexo
        "Marquei com o Leo para instalar",           # Informação + contexto
        "Beleza, pode deixar assim",                  # Finalizer com contexto
        "Como está o andamento da obra?",            # Pergunta técnica
        "Preciso do romaneio urgente",               # Pedido direto
        "Valeu pela atenção",                        # Agradecimento
    ]
    
    from main import is_finalizing_message
    
    # Importar/simular outras funções que não são exportadas
    import re
    
    # Padrões importantes do código
    GREETINGS_RE = re.compile(
        r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))',
        re.I
    )
    
    FOLLOWUP_RE = re.compile(
        r'\b(deu certo|e (ai|a[ií])\?|como ficou|conseguiu|e sobre|e aquela|e o? que|tem novidade|me fala|me retorna|resposta|atualiza)\b',
        re.I
    )
    
    # Palavras técnicas
    technical_keywords = [
        "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
        "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
        "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
        "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
        "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando",
        "como", "onde", "qual", "quando", "consegue", "pode", "tem", "instalar"
    ]
    
    print("🔍 ANALISANDO CADA MENSAGEM:")
    print("=" * 80)
    
    for i, msg in enumerate(test_messages, 1):
        print(f"\n{i:2d}. '{msg}'")
        
        txt_lower = msg.lower()
        
        # 1. FINALIZER CHECK
        is_finalizer = is_finalizing_message(msg)
        print(f"    🏁 is_finalizing_message: {is_finalizer}")
        
        # 2. GREETING CHECK  
        is_greeting = GREETINGS_RE.match(msg.strip()) is not None
        print(f"    👋 is_greeting: {is_greeting}")
        
        # 3. FOLLOWUP CHECK
        is_followup = FOLLOWUP_RE.search(msg) is not None
        print(f"    🔄 is_followup: {is_followup}")
        
        # 4. TECHNICAL CONTENT CHECK
        has_technical = any(keyword in txt_lower for keyword in technical_keywords)
        technical_found = [k for k in technical_keywords if k in txt_lower]
        print(f"    🔧 has_technical: {has_technical}")
        if technical_found:
            print(f"        Keywords: {technical_found[:5]}{'...' if len(technical_found) > 5 else ''}")
        
        # 5. SIMULAR LÓGICA DE SMALLTALK  
        smalltalk = is_greeting and (not is_finalizer) and (not has_technical)
        print(f"    💬 seria_smalltalk: {smalltalk}")
        
        # 6. RESULTADO FINAL
        if is_finalizer:
            result = "🚫 BLOCKED: ignored_finalizer"
        elif smalltalk:
            result = "🚫 BLOCKED: smalltalk (resposta de saudação)"
        else:
            result = "✅ PASSA: vai para IA processar"
        
        print(f"    ➡️  {result}")
        
        # 7. IDENTIFICAR PROBLEMAS
        if is_greeting and has_technical and not smalltalk:
            print(f"    ✅ CORRETO: Greeting + técnico vai para IA")
        elif is_greeting and not has_technical and smalltalk:
            print(f"    ✅ CORRETO: Greeting puro vira smalltalk")
        elif is_finalizer and has_technical:
            print(f"    ⚠️  ATENÇÃO: Conteúdo técnico sendo bloqueado por finalizer!")
        elif not is_greeting and not is_finalizer and not has_technical and not smalltalk:
            print(f"    ⚠️  ATENÇÃO: Mensagem sem classificação clara!")

if __name__ == "__main__":
    analyze_all_flow_interceptors()