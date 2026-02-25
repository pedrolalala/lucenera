#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste final do sistema de refinamento após remoção da exclusão de ambíguas
"""

import os
os.environ["SKIP_FLASK_INIT"] = "1"
os.environ["ENABLE_RESPONSE_REFINEMENT"] = "true"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_refinement_with_ambiguous():
    """Teste completo incluindo mensagens ambíguas"""
    print("🎯 Teste Final - Refinamento incluindo Ambíguas")
    print("=" * 55)
    
    test_cases = [
        {
            "name": "Mariane - Orçamento (era ambigua)",
            "msg": "Gostaria de orçar o pendente floatation de 75cm de diâmetro"
        },
        {
            "name": "Priscila - Eletricista (pergunta)",  
            "msg": "Oi, me disseram que vocês tem profissionais eletrecista. Na quinta feira preciso de um para vistoriar o quadro de luz. Conseguem?"
        },
        {
            "name": "Henrique - Dr. Altino (específica)",
            "msg": "Oi, você sabe me informar se o Dr Altino está passando bem?"
        }
    ]
    
    try:
        from main import (_identify_message_type, _generate_contextual_response_by_type, 
                         refine_response_with_ai, _get_conversation_context, ENABLE_RESPONSE_REFINEMENT)
        
        print(f"REFINEMENT ENABLED: {ENABLE_RESPONSE_REFINEMENT}")
        print()
        
        for i, case in enumerate(test_cases, 1):
            print(f"{i}. {case['name']}")
            print(f"   Mensagem: {case['msg']}")
            
            # 1. Classificação
            msg_type = _identify_message_type(case['msg'])
            print(f"   Classificação: {msg_type}")
            
            # 2. Resposta contextual base
            contextual_response = _generate_contextual_response_by_type(case['msg'], msg_type)
            print(f"   Base: {contextual_response}")
            
            # 3. Refinamento com IA (se habilitado)
            if ENABLE_RESPONSE_REFINEMENT:
                try:
                    conversation_context = _get_conversation_context(None)  # Sem telefone para teste
                    refined = refine_response_with_ai(
                        user_message=case['msg'],
                        base_response=contextual_response,
                        conversation_history=conversation_context
                    )
                    print(f"   ✅ Refinada: {refined}")
                    
                    if refined != contextual_response:
                        print(f"   🎉 REFINAMENTO APLICADO!")
                    else:
                        print(f"   ⚠️ Sem alteração")
                        
                except Exception as e:
                    print(f"   ❌ Erro no refinamento: {e}")
            else:
                print(f"   ⚠️ Refinamento desabilitado")
                
            print()
            
    except Exception as e:
        print(f"❌ ERRO no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_refinement_with_ambiguous()