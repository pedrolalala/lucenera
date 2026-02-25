import os
import sys
sys.path.insert(0, os.getcwd())

def analyze_problematic_cases():
    """Analisa casos específicos que podem estar sendo mal classificados"""
    
    print("=== ANÁLISE DE CASOS PROBLEMÁTICOS ===")
    print()
    
    # Casos potencialmente problemáticos
    edge_cases = [
        "Beleza, pode deixar assim",                    # finalizer + instrução
        "Ok, mas precisa mudar o projeto",             # finalizer + pedido  
        "Obrigado, quando fica pronto?",               # finalizer + pergunta
        "Certo, pode instalar amanhã",                 # finalizer + instrução
        "Perfeito, vou mandar o desenho",              # finalizer + ação
        "Tranquilo, consegue entregar hoje?",          # finalizer + pergunta
        "Show, qual o valor final?",                   # finalizer + pergunta
        "Entendi, mas e o orçamento?",                 # finalizer + mas + pergunta
        "Combinado, vou aguardar o material",          # finalizer + aguardo
        "Fechou, quando vem o técnico?",               # finalizer + pergunta
    ]
    
    from main import is_finalizing_message
    
    # Palavras técnicas
    technical_keywords = [
        "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
        "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
        "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
        "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
        "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando",
        "como", "onde", "qual", "quando", "consegue", "pode", "tem", "instalar", "entregar", "técnico"
    ]
    
    print("🚨 CASOS EDGE (finalizer + conteúdo):")
    print("=" * 70)
    
    problematic_count = 0
    
    for i, msg in enumerate(edge_cases, 1):
        print(f"\n{i:2d}. '{msg}'")
        
        txt_lower = msg.lower()
        
        # Checks
        is_finalizer = is_finalizing_message(msg)
        has_technical = any(keyword in txt_lower for keyword in technical_keywords)
        technical_found = [k for k in technical_keywords if k in txt_lower]
        
        print(f"    🏁 is_finalizer: {is_finalizer}")
        print(f"    🔧 has_technical: {has_technical}")
        if technical_found:
            print(f"        Keywords: {technical_found}")
        
        # Identificar se há pergunta ou condicional
        has_question = "?" in msg
        has_conditional = any(word in txt_lower for word in ["mas", "porém", "entretanto", "contudo", "e o", "e a"])
        
        print(f"    ❓ has_question: {has_question}")
        print(f"    🤔 has_conditional: {has_conditional}")
        
        # PROBLEMA: Se é finalizer MAS tem pergunta/condicional/conteúdo técnico
        is_problematic = is_finalizer and (has_question or has_conditional or has_technical)
        
        if is_problematic:
            problematic_count += 1
            print(f"    🚨 PROBLEMA: Finalizer bloqueando conteúdo relevante!")
            print(f"       Deveria ir para IA processar, mas será ignored_finalizer")
        else:
            print(f"    ✅ OK: Classificação correta")
    
    print(f"\n📊 RESUMO:")
    print(f"   Total de casos analisados: {len(edge_cases)}")
    print(f"   Casos problemáticos: {problematic_count}")
    
    if problematic_count > 0:
        print(f"\n💡 SOLUÇÃO SUGERIDA:")
        print("   Modificar is_finalizing_message() para ser menos agressivo")
        print("   quando há conteúdo técnico, perguntas ou condicionais")

if __name__ == "__main__":
    analyze_problematic_cases()