#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste rápido e direto do sistema de refinamento
"""

# Configurar ambiente mínimo sem inicializar o Flask
import os
os.environ["SKIP_FLASK_INIT"] = "1"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_direct():
    """Teste direto das funções de refinamento"""
    print("🔧 Teste Direto do Sistema de Refinamento")
    print("=" * 50)
    
    # Simular mensagem de teste
    original_msg = "Gostaria de orçar o pendente floatation de 75cm de diâmetro"
    resposta_base = "Julia: Vou verificar e te retorno com as informações"
    sender_name = "Mariane"
    
    print(f"Mensagem: {original_msg}")
    print(f"Resposta Base: {resposta_base}")
    
    # Importar função após configurar ambiente
    try:
        # Simular ENABLE_RESPONSE_REFINEMENT=True 
        os.environ["ENABLE_RESPONSE_REFINEMENT"] = "true"
        
        # Importar funções necessárias 
        from main import _identify_message_type, _generate_contextual_response_by_type
        
        # Testar classificação
        msg_type = _identify_message_type(original_msg)
        print(f"Tipo Identificado: {msg_type}")
        
        # Testar geração contextual
        contextual_response = _generate_contextual_response_by_type(original_msg, msg_type)
        print(f"Resposta Contextual: {contextual_response}")
        
        # Verificar se é diferente da resposta base
        if contextual_response != resposta_base:
            print("✅ SISTEMA FUNCIONANDO - Resposta contextual gerada!")
        else:
            print("⚠️ Sistema não alterou a resposta")
            
        print(f"REFINEMENT ENABLED: {os.getenv('ENABLE_RESPONSE_REFINEMENT')}")
        
    except Exception as e:
        print(f"❌ ERRO no teste: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_direct()