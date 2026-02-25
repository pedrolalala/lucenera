#!/usr/bin/env python3
"""
Teste para verificar se a duplicação de mensagens no Teams foi corrigida.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_duplication_fix():
    """Testa se há apenas uma definição da função _teams_notify no código."""
    
    # Ler o arquivo main.py
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Contar quantas vezes aparece "def _teams_notify"
    count = content.count("def _teams_notify(")
    
    print(f"🧪 Verificando duplicação de função _teams_notify...")
    print(f">> Encontradas {count} definições de _teams_notify")
    
    if count == 1:
        print("✅ SUCESSO: Apenas uma definição de _teams_notify encontrada")
        return True
    else:
        print(f"❌ ERRO: {count} definições encontradas, esperado apenas 1")
        return False

def test_notify_received_logic():
    """Testa a lógica corrigida da função _notify_received_message_processed."""
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Verificar se a lógica foi corrigida
    notify_func_start = content.find("def _notify_received_message_processed")
    if notify_func_start == -1:
        print("❌ ERRO: Função _notify_received_message_processed não encontrada")
        return False
        
    # Encontrar o final da função (próxima função)
    next_func = content.find("\ndef ", notify_func_start + 1)
    if next_func == -1:
        next_func = len(content)
    
    func_content = content[notify_func_start:next_func]
    
    print("🧪 Verificando lógica de _notify_received_message_processed...")
    
    # Verificar se a correção foi aplicada
    if 'current_status != "ignored_finalizer"' in func_content:
        print("✅ SUCESSO: Lógica corrigida - só envia para ignored_finalizer")
        return True
    else:
        print("❌ ERRO: Lógica não corrigida")
        return False

if __name__ == "__main__":
    print("🔧 Testando correção de duplicação no Teams...\n")
    
    test1 = test_duplication_fix()
    test2 = test_notify_received_logic()
    
    if test1 and test2:
        print("\n🎉 TODOS OS TESTES PASSARAM - Duplicação corrigida!")
    else:
        print("\n❌ ALGUNS TESTES FALHARAM - Verificar correções")