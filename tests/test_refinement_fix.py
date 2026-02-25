#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste rápido para verificar se o sistema de refinamento está funcionando
após as correções no fluxo principal.
"""

import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import _humanize_robotic_response

def test_refinement_activation():
    """Testa se o sistema de refinamento está sendo ativado corretamente."""
    
    print("🔧 Testando Ativação do Sistema de Refinamento")
    print("=" * 60)
    
    # Casos de teste das mensagens que estavam falhando
    test_cases = [
        {
            "name": "Priscila - Eletrecista",
            "resposta_base": "Julia: Vou verificar e te retorno com as informações",
            "sender_name": "Priscila",
            "original_msg": "Oi, me disseram que vocês tem profissionais eletrecista. Na quinta feira preciso de um para vistoriar o quadro de luz. Conseguem?"
        },
        {
            "name": "Henrique - Dr. Altino",  
            "resposta_base": "Julia: Vou verificar e te retorno com as informações",
            "sender_name": "Henrique",
            "original_msg": "Oi, você sabe me informar se o Dr Altino está passando bem?"
        },
        {
            "name": "Mariane - Pendente Floatation",
            "resposta_base": "Julia: Para o pendente Floatation de 75 cm de diâmetro, vou verificar a disponibilidade e o preço",
            "sender_name": "Mariane",  
            "original_msg": "Oie Thais, tudo bom? Gostaria de orçar o pendente floatation de 75cm de diâmetro com vocês."
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}")
        print(f"   Mensagem: {case['original_msg']}")
        print(f"   Resposta Base: {case['resposta_base']}")
        
        try:
            # Testar o sistema de humanização/refinamento
            refined = _humanize_robotic_response(
                resposta=case['resposta_base'],
                sender_name=case['sender_name'], 
                original_msg=case['original_msg']
            )
            
            print(f"   ✅ Refinada: {refined}")
            
            # Verificar se houve refinamento real
            if refined != case['resposta_base']:
                print(f"   🎉 REFINAMENTO APLICADO!")
            else:
                print(f"   ⚠️  Nenhuma mudança detectada")
                
        except Exception as e:
            print(f"   ❌ ERRO: {e}")
    
    print("\n" + "=" * 60)
    print("Teste concluído!")

if __name__ == "__main__":
    test_refinement_activation()