import os
import sys
sys.path.insert(0, os.getcwd())

def test_marina_messages():
    """Testa as duas mensagens específicas da Marina"""
    
    from main import is_finalizing_message
    import re
    
    # As duas mensagens da Marina
    messages = [
        ("Marina v1 (com 47cm)", "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final"),
        ("Marina v2 (sem 47cm)", "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final")
    ]
    
    # Simular todas as verificações do fluxo
    GREETINGS_RE = re.compile(r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))', re.I)
    
    # Palavras técnicas (mesmo conjunto que usamos nas correções)
    technical_keywords = [
        "projeto", "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis",
        "luminária", "ponto", "iluminação", "beiral", "gesso", "traçado", "layout", 
        "estoque", "retirar", "conseguir", "disponível", "separar", "romaneio", "itens", "material",
        "watts", "temperatura", "voltagem", "medida", "dimensão", "modelo", "especificação",
        "preço", "valor", "quanto", "orçamento", "prazo", "entrega", "quando", "instalar",
        "como", "onde", "qual", "consegue", "pode", "tem", "técnico", "entregar"
    ]
    
    # Padrões de projeto para humanização
    projeto_patterns = [
        "projeto", "luminária", "luminaria", "ponto", "acrescentar", "iluminação", "iluminacao",
        "beiral", "gesso", "traçado", "layout", "porro", "garagem", "manter assim", "confirmar",
        "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis"
    ]
    
    print("=== TESTE COMPLETO DAS MENSAGENS DA MARINA ===")
    print()
    
    for name, msg in messages:
        print(f"📋 {name}")
        print(f"Mensagem: '{msg}'")
        print()
        
        txt_lower = msg.lower()
        
        # 1. VERIFICAÇÕES DE INTERCEPTAÇÃO
        is_finalizer = is_finalizing_message(msg)
        is_greeting = GREETINGS_RE.match(msg.strip()) is not None
        has_technical = any(keyword in txt_lower for keyword in technical_keywords)
        
        print(f"🔍 VERIFICAÇÕES:")
        print(f"   🏁 is_finalizing_message: {is_finalizer}")
        print(f"   👋 is_greeting: {is_greeting}")
        print(f"   🔧 has_technical_content: {has_technical}")
        
        technical_found = [k for k in technical_keywords if k in txt_lower]
        print(f"   📝 Technical keywords: {technical_found}")
        
        # 2. VERIFICAR SE PASSA POR FINALIZER
        if is_finalizer:
            # Nova lógica de finalizer
            has_question = "?" in msg
            has_conditional = any(word in txt_lower for word in ["mas", "porém", "e o", "e a"])
            has_future_action = any(phrase in txt_lower for phrase in ["vou mandar", "vou enviar", "vou aguardar"])
            
            if has_technical or has_question or has_conditional or has_future_action:
                finalizer_result = "✅ PASSA (finalizer + conteúdo) → vai para IA"
            else:
                finalizer_result = "🚫 BLOCKED: ignored_finalizer"
        else:
            finalizer_result = "✅ PASSA (não é finalizer) → vai para IA"
        
        print(f"   🎯 Finalizer check: {finalizer_result}")
        
        # 3. VERIFICAR SE PASSA POR SMALLTALK  
        if "PASSA" in finalizer_result:
            # Verificar smalltalk
            smalltalk_condition = is_greeting and (not is_finalizer) and (not has_technical)
            if smalltalk_condition:
                smalltalk_result = "🚫 BLOCKED: smalltalk → resposta de saudação"
            else:
                smalltalk_result = "✅ PASSA → vai para IA processar conteúdo completo"
        else:
            smalltalk_result = "N/A (já bloqueado por finalizer)"
            
        print(f"   💬 Smalltalk check: {smalltalk_result}")
        
        # 4. SE CHEGOU NA IA, SIMULAR HUMANIZAÇÃO
        if "✅ PASSA → vai para IA" in smalltalk_result:
            print(f"\n🤖 PROCESSAMENTO DA IA:")
            print(f"   📥 Mensagem vai para ChatGPT...")
            print(f"   🔄 ChatGPT provavelmente retorna algo robótico...")
            print(f"   🎭 Passa por _humanize_robotic_response()...")
            
            # Verificar se seria capturado pelos padrões de projeto
            projeto_match = [p for p in projeto_patterns if p in txt_lower]
            if projeto_match:
                print(f"   ✅ CAPTURADO por projeto_patterns: {projeto_match}")
                expected_response = "Julia: Vou confirmar com a equipe responsável pelo projeto e te retorno com a validação"
            else:
                print(f"   ❌ NÃO capturado - cairia no fallback")
                expected_response = "Julia: Vou verificar e te retorno com as informações"
                
            print(f"   📤 RESPOSTA FINAL: '{expected_response}'")
            
        elif "smalltalk" in smalltalk_result:
            print(f"\n💬 PROCESSAMENTO SMALLTALK:")
            expected_response = "Julia: Boa tarde! Tudo ótimo, e você? Como posso ajudar?"
            print(f"   📤 RESPOSTA FINAL: '{expected_response}'")
            
        else:
            print(f"\n🚫 BLOQUEADO:")
            print(f"   📤 SEM RESPOSTA (ignored_finalizer)")
        
        print("=" * 80)
        print()

if __name__ == "__main__":
    test_marina_messages()