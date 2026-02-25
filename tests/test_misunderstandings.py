#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste específico dos casos de mal-entendidos
"""

import os
os.environ["SKIP_FLASK_INIT"] = "1" 
os.environ["ENABLE_RESPONSE_REFINEMENT"] = "true"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_misunderstanding_fixes():
    """Teste focado nos mal-entendidos"""
    print("🎯 Teste Específico - Correção de Mal-entendidos")
    print("=" * 55)
    
    test_cases = [
        {
            "name": "Eletricista",
            "msg": "Vocês tem eletricista para quinta feira?",
            "base": "Vou verificar a disponibilidade e te confirmo",
        },
        {
            "name": "Dr. Altino", 
            "msg": "O Dr Altino está bem?",
            "base": "Vou verificar essa informação e te retorno",
        },
        {
            "name": "Orçamento Normal",
            "msg": "Quero orçar uma luminária de teto",
            "base": "Vou verificar e te retorno",
        }
    ]
    
    try:
        from main import refine_response_with_ai
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n{i}. Teste: {case['name']}")
            print(f"   Mensagem: {case['msg']}")
            print(f"   Base: {case['base']}")
            
            refined = refine_response_with_ai(
                user_message=case['msg'],
                base_response=case['base'],
                conversation_history=""
            )
            
            print(f"   ✨ Refinada: {refined}")
            
            # Análise manual
            if case['name'] == "Eletricista":
                if "especializados em" in refined.lower() and "não oferecemos" in refined.lower():
                    print(f"   ✅ CORREÇÃO APLICADA - Esclareceu que não oferece eletricista")
                else:
                    print(f"   ❌ FALHOU - Não corrigiu o mal-entendido")
                    
            elif case['name'] == "Dr. Altino":
                if "não temos informações" in refined.lower():
                    print(f"   ✅ CORREÇÃO APLICADA - Esclareceu sobre pessoa externa")
                else:
                    print(f"   ❌ FALHOU - Não corrigiu o mal-entendido")
                    
            elif case['name'] == "Orçamento Normal":
                if "orçamento" in refined.lower() or "valores" in refined.lower():
                    print(f"   ✅ ESPECÍFICO - Mencionou orçamento/valores") 
                else:
                    print(f"   ⚠️ GENÉRICO - Não mencionou orçamento específico")
            
    except Exception as e:
        print(f"💥 ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_misunderstanding_fixes()