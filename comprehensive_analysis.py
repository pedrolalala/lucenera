import os
import sys
sys.path.insert(0, os.getcwd())

def comprehensive_flow_analysis():
    """Análise completa de todos os interceptadores e suas correções necessárias"""
    
    print("=== ANÁLISE COMPLETA E PROPOSTAS DE CORREÇÃO ===")
    print()
    
    # Casos reais que devem ser testados
    real_cases = [
        ("Marina", "Boa tarde! A profundidade que você perguntou: O PD acabado vou te mandar a planta de forro final"),
        ("Bruno", "Marquei com o Leo para instalar. Consegue os perfis para amanhã??"),
        ("Saulo", "Pode deixar"),
        ("Henry", "Entendi vou repassar para o Airton"),
        ("Edge1", "Perfeito, vou mandar o desenho"),
        ("Edge2", "Combinado, vou aguardar o material"),
        ("Edge3", "Ok, mas precisa mudar o projeto"),
        ("Edge4", "Obrigado, quando fica pronto?"),
        ("Valid1", "Qual o preço do perfil L35?"),
        ("Valid2", "Preciso do romaneio urgente"),
    ]
    
    from main import is_finalizing_message
    import re
    
    # Simular outras funções
    GREETINGS_RE = re.compile(r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))', re.I)
    
    def _safe_is_followup_sim(texto):
        t = (texto or "").lower()
        return any(p in t for p in ["deu certo","como ficou","e aí","e ai","conseguiu","e sobre"])
    
    def _safe_is_logistica_sim(texto):
        t = (texto or "").lower()
        return any(p in t for p in ["entrega","prazo","rastre","instala","retirada","nota fiscal","nf","troca","devolu","garantia","led","driver","spot","luminaria","luminária"])
    
    def _needs_clarify_sim(texto):
        # Simular lógica básica
        t = texto.lower()
        vague_terms = ["preco","preço","quanto custa","valores","orçamento","orcamento"]
        domain_terms = ["perfil","led","spot","luminaria","projeto","driver"]
        
        if any(v in t for v in vague_terms) and not any(d in t for d in domain_terms):
            return "De qual produto/medida você precisa o preço?"
        return None
    
    # Palavras técnicas expandidas
    technical_keywords = [
        "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
        "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
        "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
        "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
        "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando", "instalar",
        "como", "onde", "qual", "consegue", "pode", "tem", "técnico", "entregar"
    ]
    
    print("🔍 ANÁLISE CASO A CASO:")
    print("=" * 100)
    
    problems_found = []
    
    for name, msg in real_cases:
        print(f"\n📋 {name}: '{msg}'")
        
        txt_lower = msg.lower()
        
        # Todos os checks
        is_finalizer = is_finalizing_message(msg)
        is_greeting = GREETINGS_RE.match(msg.strip()) is not None
        is_followup = _safe_is_followup_sim(msg)
        is_logistica = _safe_is_logistica_sim(msg)
        needs_clarify = _needs_clarify_sim(msg)
        has_technical = any(keyword in txt_lower for keyword in technical_keywords)
        has_question = "?" in msg
        has_conditional = any(word in txt_lower for word in ["mas", "porém", "e o", "e a"])
        
        print(f"   🏁 Finalizer: {is_finalizer}")
        print(f"   👋 Greeting: {is_greeting}")
        print(f"   🔄 Followup: {is_followup}")
        print(f"   📦 Logística: {is_logistica}")
        print(f"   ❓ Needs clarify: {needs_clarify is not None}")
        print(f"   🔧 Technical: {has_technical}")
        print(f"   ❓ Question: {has_question}")
        print(f"   🤔 Conditional: {has_conditional}")
        
        # Determinar fluxo atual
        if is_finalizer:
            current_flow = "🚫 BLOCKED: ignored_finalizer"
        elif is_greeting and not has_technical:
            current_flow = "🚫 BLOCKED: smalltalk"  
        elif needs_clarify:
            current_flow = "🔄 CLARIFY: pergunta para especificar"
        else:
            current_flow = "✅ AI: processa conteúdo"
            
        print(f"   ➡️  {current_flow}")
        
        # Identificar problemas
        problem = None
        if is_finalizer and (has_technical or has_question or has_conditional):
            problem = "Finalizer bloqueando conteúdo importante"
        elif is_greeting and has_technical and msg == real_cases[0][1]:  # Marina
            if "smalltalk" in current_flow:
                problem = "Greeting bloqueando conteúdo técnico (corrigido)"
        elif needs_clarify and has_technical:
            problem = "Clarify desnecessário para conteúdo específico"
            
        if problem:
            problems_found.append((name, problem, msg))
            print(f"   🚨 PROBLEMA: {problem}")
        else:
            print(f"   ✅ OK")
    
    print(f"\n📊 RESUMO DOS PROBLEMAS ENCONTRADOS:")
    print("=" * 60)
    
    for i, (name, problem, msg) in enumerate(problems_found, 1):
        print(f"{i}. {name}: {problem}")
        print(f"   Mensagem: '{msg[:50]}{'...' if len(msg) > 50 else ''}'")
    
    print(f"\n💡 CORREÇÕES NECESSÁRIAS:")
    print("=" * 60)
    
    print("1. 🏁 FINALIZERS - Tornar menos agressivo:")
    print("   - Se tem conteúdo técnico + finalizer → Vai para IA")
    print("   - Se tem pergunta + finalizer → Vai para IA") 
    print("   - Se tem condicional + finalizer → Vai para IA")
    print()
    
    print("2. 👋 GREETINGS - Já corrigido:")
    print("   - Greeting + técnico → Vai para IA ✅")
    print()
    
    print("3. ❓ CLARIFY - Tornar mais específico:")
    print("   - Só para casos realmente vagos")
    print("   - Não bloquear conteúdo técnico específico")

if __name__ == "__main__":
    comprehensive_flow_analysis()