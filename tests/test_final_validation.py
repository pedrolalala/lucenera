#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste final simplificado para validar correções de padrões inadequados
"""

import sys
import os

# Adiciona o diretório raiz ao PATH para imports
sys.path.insert(0, os.path.dirname(__file__))
from main import _humanize_robotic_response

def test_validation():
    """Testa todos os casos que estavam falhando para verificar se agora passam"""
    
    print("=== VALIDACAO FINAL DE CORRECOES ===")
    
    # Casos que estavam falhando no teste original
    casos_problematicos = [
        # Casos de saudação para conteúdo técnico
        ("Bom dia! O projeto da luminária ficou pronto?", "**Julia:** Olá! Tudo certo por aqui, e aí?"),
        ("Oi, consegue me mandar o layout do gesso?", "**Julia:** Tudo tranquilo, obrigada por perguntar!"),
        ("Qual a potência em watts desse LED?", "**Julia:** Tudo tranquilo, obrigada por perguntar!"),
        ("Bom dia! Mandei um arquivo por email", "**Julia:** Bom dia! Tudo ótimo, e com você?"),
        
        # Casos de urgência que não estavam sendo corrigidos
        ("Preciso urgente do orçamento da obra", "**Julia:** Compreendo, vou analisar e retornar"),
        ("URGENTE: Cliente esperando a entrega hoje", "**Julia:** Ok, vou dar uma olhada"),
        ("LED queimou, cliente reclamando, preciso trocar", "**Julia:** Perfeito, vou analisar"),
    ]
    
    total_casos = len(casos_problematicos)
    casos_corrigidos = 0
    
    for i, (mensagem, resposta_ruim) in enumerate(casos_problematicos):
        resultado = _humanize_robotic_response(resposta_ruim, "Cliente", mensagem)
        
        foi_corrigido = resultado != resposta_ruim
        if foi_corrigido:
            casos_corrigidos += 1
        
        status = "✓ CORRIGIDO" if foi_corrigido else "✗ NAO CORRIGIDO"
        
        print(f"\n{i+1}. {status}")
        print(f"   Mensagem: {mensagem[:60]}...")
        print(f"   Original: {resposta_ruim[:60]}...")
        print(f"   Corrigido: {resultado[:60]}...")
    
    print(f"\n=== RESULTADO FINAL ===")
    print(f"Total de casos testados: {total_casos}")
    print(f"Casos corrigidos: {casos_corrigidos}")
    print(f"Taxa de sucesso: {casos_corrigidos/total_casos*100:.1f}%")
    
    if casos_corrigidos == total_casos:
        print("🎉 TODOS OS CASOS FORAM CORRIGIDOS COM SUCESSO!")
    else:
        print(f"⚠️  Ainda restam {total_casos - casos_corrigidos} casos para corrigir")

if __name__ == "__main__":
    test_validation()