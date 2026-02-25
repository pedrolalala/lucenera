#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste Abrangente das Melhorias no Sistema de Refinamento
Testa: Base de conhecimento, correção de mal-entendidos, especificidade comercial e redução de padrões robóticos
"""

import os
os.environ["SKIP_FLASK_INIT"] = "1"
os.environ["ENABLE_RESPONSE_REFINEMENT"] = "true"

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def test_improved_refinement():
    """Testa todas as melhorias implementadas no sistema de refinamento"""
    print("🚀 Teste das Melhorias no Sistema de Refinamento")
    print("=" * 65)
    
    test_cases = [
        # 1. Especificidade Comercial - Orçamento
        {
            "category": "Especificidade Comercial",
            "name": "Mariane - Orçamento Floatation",
            "msg": "Gostaria de orçar o pendente floatation de 75cm de diâmetro",
            "base_response": "Vou verificar e te retorno com as informações",
            "should_contain": ["orçamento", "valores", "floatation", "75cm"],
            "should_not_contain": ["vou verificar e te retorno"]
        },
        
        # 2. Correção de Mal-entendido - Eletricista
        {
            "category": "Correção de Mal-entendido",
            "name": "Priscila - Eletricista (NÃO oferecemos)",
            "msg": "Vocês tem profissionais eletricista para vistoriar o quadro de luz na quinta?",
            "base_response": "Vou verificar a disponibilidade e te confirmo",
            "should_contain": ["especializados em iluminação", "eletricista credenciado"],
            "should_not_contain": ["vou verificar eletricista", "nossa equipe de eletricista"]
        },
        
        # 3. Correção de Contexto - Pessoa Externa
        {
            "category": "Correção de Contexto",
            "name": "Henrique - Dr. Altino (pessoa externa)",
            "msg": "Você sabe me informar se o Dr Altino está passando bem?",
            "base_response": "Vou verificar essa informação e te retorno",
            "should_contain": ["não temos informações", "especializados em iluminação"],
            "should_not_contain": ["vou verificar como ele está", "vou perguntar sobre"]
        },
        
        # 4. Redução de Padrões Robóticos - Variação
        {
            "category": "Redução de Padrões Robóticos",
            "name": "Cliente - Consulta de Estoque",
            "msg": "Vocês têm luminária de teto disponível?",
            "base_response": "Vou verificar o estoque e te retorno",
            "should_contain_any": ["vou confirmar", "vou dar uma olhada", "vou checar"],
            "should_not_contain": ["vou verificar e te retorno"]
        },
        
        # 5. Manutenção de Ação Principal
        {
            "category": "Manutenção de Ação",
            "name": "Cliente - Agendamento",
            "msg": "Gostaria de agendar uma visita técnica",
            "base_response": "Vou alinhar com a equipe e retorno com as opções de horário",
            "should_contain": ["alinhar", "equipe", "horário"],
            "should_not_contain": []
        }
    ]
    
    try:
        from main import refine_response_with_ai, _validate_refined_response
        
        success_count = 0
        total_count = len(test_cases)
        
        for i, case in enumerate(test_cases, 1):
            print(f"\n{i}. [{case['category']}] {case['name']}")
            print(f"   Mensagem: {case['msg']}")
            print(f"   Base: {case['base_response']}")
            
            try:
                # Testar refinamento
                refined = refine_response_with_ai(
                    user_message=case['msg'],
                    base_response=case['base_response'],
                    conversation_history="Cliente: Oi | Julia: Oi!"
                )
                
                print(f"   ✨ Refinada: {refined}")
                
                # Validar resultado
                validation_passed = True
                issues = []
                
                # Verificar termos obrigatórios
                if 'should_contain' in case:
                    for term in case['should_contain']:
                        if term.lower() not in refined.lower():
                            validation_passed = False
                            issues.append(f"Faltou '{term}'")
                
                # Verificar termos que devem estar (pelo menos um)
                if 'should_contain_any' in case:
                    found_any = any(term.lower() in refined.lower() for term in case['should_contain_any'])
                    if not found_any:
                        validation_passed = False
                        issues.append(f"Não contém nenhum de: {case['should_contain_any']}")
                
                # Verificar termos proibidos
                if 'should_not_contain' in case:
                    for term in case['should_not_contain']:
                        if term.lower() in refined.lower():
                            validation_passed = False
                            issues.append(f"Contém termo proibido '{term}'")
                
                # Testar validação interna
                internal_validation = _validate_refined_response(refined, case['base_response'], case['msg'])
                if not internal_validation:
                    validation_passed = False
                    issues.append("Falhou na validação interna")
                
                # Resultado
                if validation_passed:
                    print(f"   ✅ PASSOU - Refinamento adequado!")
                    success_count += 1
                else:
                    print(f"   ❌ FALHOU - Problemas: {', '.join(issues)}")
                    
            except Exception as e:
                print(f"   💥 ERRO: {e}")
        
        print(f"\n" + "=" * 65)
        print(f"📊 Resultado Final: {success_count}/{total_count} testes passaram")
        print(f"Taxa de Sucesso: {(success_count/total_count)*100:.1f}%")
        
        if success_count == total_count:
            print("🎉 TODAS AS MELHORIAS IMPLEMENTADAS COM SUCESSO!")
        else:
            print("⚠️  Ainda há problemas a serem corrigidos")
            
    except Exception as e:
        print(f"💥 ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_improved_refinement()