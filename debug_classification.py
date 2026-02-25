#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Debug da classificação de mensagens - por que "orçar pendente" = ambigua?
"""

import os
os.environ["SKIP_FLASK_INIT"] = "1"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def debug_classification():
    """Debug do processo de classificação"""
    print("🔍 Debug da Classificação de Mensagens")
    print("=" * 50)
    
    test_cases = [
        "Gostaria de orçar o pendente floatation de 75cm de diâmetro",
        "Oie Thais, tudo bom? Gostaria de orçar o pendente floatation de 75cm de diâmetro com vocês",
        "Quero saber o preço do pendente floatation",
        "Conseguem fazer orçamento de luminária?",
        "Quanto custa o pendente de 75cm?"
    ]
    
    try:
        from main import _identify_message_type
        
        for i, msg in enumerate(test_cases, 1):
            msg_type = _identify_message_type(msg)
            print(f"{i}. '{msg}'")
            print(f"   → Classificação: {msg_type}")
            print()
            
    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_classification()