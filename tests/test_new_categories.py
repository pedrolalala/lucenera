#!/usr/bin/env python3
"""
Script para testar as novas categorias de respostas automáticas:
- MENSAGEM ESPECÍFICA (PIX, orçamento, catálogo, entrega, retirada, exclusividade)
- AGENDAMENTO (material, reunião, entrega)
"""

import sys
import os

# Adicionar o diretório principal ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importar as funções do sistema principal
from main import _identify_message_type, _generate_contextual_response_by_type, _get_time_greeting

def test_message_category(message, expected_category, description):
    """Testa uma mensagem e verifica se foi classificada corretamente."""
    detected_category = _identify_message_type(message)
    
    print(f"\n=== {description} ===")
    print(f"Mensagem: \"{message}\"")
    print(f"Categoria esperada: {expected_category}")
    print(f"Categoria detectada: {detected_category}")
    
    # Verificar se a categoria está correta
    success = detected_category == expected_category
    status = "✅ SUCESSO" if success else "❌ FALHOU"
    print(f"Status: {status}")
    
    if success:
        # Se a categoria está correta, testar a resposta
        response = _generate_contextual_response_by_type(message, detected_category)
        print(f"Resposta gerada: \"{response}\"")
    else:
        print(f"⚠️  Esperava '{expected_category}' mas detectou '{detected_category}'")
    
    return success

def run_tests():
    """Executa todos os testes das novas categorias."""
    print("🚀 TESTANDO NOVAS CATEGORIAS DE RESPOSTAS AUTOMÁTICAS")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 0
    
    # ===== CATEGORIA: MENSAGENS ESPECÍFICAS =====
    print("\n🎯 CATEGORIA 1: MENSAGENS ESPECÍFICAS")
    
    # 1. PIX/PAGAMENTO
    tests = [
        ("Qual a chave PIX?", "mensagem_especifica", "PIX - Pergunta sobre chave"),
        ("Preciso dos dados bancários", "mensagem_especifica", "PIX - Dados bancários"),
        ("Pode me passar os dados para pagamento?", "mensagem_especifica", "PIX - Dados pagamento"),
        ("Como faço a transferência?", "mensagem_especifica", "PIX - Transferência"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 2. ORÇAMENTO
    tests = [
        ("Preciso de um orçamento", "mensagem_especifica", "Orçamento - Solicitação"),
        ("Pode fazer uma proposta?", "mensagem_especifica", "Orçamento - Proposta"),
        ("Quanto custa esse produto?", "mensagem_especifica", "Orçamento - Preço"),
        ("Quero uma cotação", "mensagem_especifica", "Orçamento - Cotação"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 3. CATÁLOGO
    tests = [
        ("Tem catálogo de produtos?", "mensagem_especifica", "Catálogo - Produtos"),
        ("Quero ver os modelos disponíveis", "mensagem_especifica", "Catálogo - Modelos"),
        ("Quais são as opções?", "mensagem_especifica", "Catálogo - Opções"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 4. ENTREGA
    tests = [
        ("Vocês entregam?", "mensagem_especifica", "Entrega - Disponibilidade"),
        ("Qual o prazo de entrega?", "mensagem_especifica", "Entrega - Prazo"),
        ("Fazem entrega em casa?", "mensagem_especifica", "Entrega - Local"),
        ("Como é o frete?", "mensagem_especifica", "Entrega - Frete"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 5. RETIRADA
    tests = [
        ("Posso retirar no estoque?", "mensagem_especifica", "Retirada - Estoque"),
        ("Quando posso ir buscar?", "mensagem_especifica", "Retirada - Quando buscar"),
        ("Vou pegar pessoalmente", "mensagem_especifica", "Retirada - Pessoalmente"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 6. EXCLUSIVIDADE/COMERCIAL
    tests = [
        ("Como funciona a exclusividade?", "mensagem_especifica", "Comercial - Exclusividade"),
        ("Quero ser revendedor", "mensagem_especifica", "Comercial - Revenda"),
        ("Trabalho com distribuição", "mensagem_especifica", "Comercial - Distribuição"),
        ("Tenho interesse em parceria", "mensagem_especifica", "Comercial - Parceria"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== CATEGORIA: AGENDAMENTO =====
    print("\n📅 CATEGORIA 2: AGENDAMENTO")
    
    # 1. AGENDAMENTO DE MATERIAL
    tests = [
        ("Posso agendar a retirada?", "agendamento", "Material - Agendar retirada"),
        ("Quando posso buscar o material?", "agendamento", "Material - Quando buscar"),
        ("Preciso marcar horário para retirar", "agendamento", "Material - Marcar horário"),
        ("Quero reservar um horário", "agendamento", "Material - Reservar"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 2. AGENDAMENTO DE REUNIÃO
    tests = [
        ("Posso marcar uma reunião?", "agendamento", "Reunião - Marcar"),
        ("Quero conversar pessoalmente", "agendamento", "Reunião - Pessoalmente"),
        ("Posso fazer uma visita?", "agendamento", "Reunião - Visita"),
        ("Vou ir aí conversar", "agendamento", "Reunião - Ir aí"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # 3. AGENDAMENTO DE ENTREGA
    tests = [
        ("Podem agendar a entrega?", "agendamento", "Entrega - Agendar"),
        ("Qual o melhor dia para entrega?", "agendamento", "Entrega - Dia"),
        ("Preciso marcar horário de entrega", "agendamento", "Entrega - Marcar horário"),
        ("Quando podem entregar?", "agendamento", "Entrega - Quando entregar"),
    ]
    
    for message, expected, desc in tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== TESTES DE PRIORIDADE =====
    print("\n⚡ TESTES DE PRIORIDADE")
    print("Verificando se as novas categorias têm prioridade sobre as genéricas...")
    
    priority_tests = [
        # Deve ser ENTREGA (específica), não PERGUNTA (genérica)
        ("Vocês entregam?", "mensagem_especifica", "Prioridade - Entrega vs Pergunta"),
        
        # Deve ser AGENDAMENTO (específica), não PERGUNTA (genérica)
        ("Quando posso agendar reunião?", "agendamento", "Prioridade - Agendamento vs Pergunta"),
        
        # Deve ser PIX (específica), não PERGUNTA (genérica)
        ("Qual a chave PIX?", "mensagem_especifica", "Prioridade - PIX vs Pergunta"),
        
        # Deve ser ORÇAMENTO (específica), não PERGUNTA (genérica)
        ("Quanto custa?", "mensagem_especifica", "Prioridade - Orçamento vs Pergunta"),
    ]
    
    for message, expected, desc in priority_tests:
        if test_message_category(message, expected, desc):
            tests_passed += 1
        total_tests += 1
    
    # ===== RESULTADO FINAL =====
    print("\n" + "=" * 60)
    print(f"📊 RESULTADO FINAL DOS TESTES")
    print(f"Total de testes: {total_tests}")
    print(f"Testes aprovados: {tests_passed}")
    print(f"Testes falharam: {total_tests - tests_passed}")
    print(f"Taxa de sucesso: {(tests_passed/total_tests)*100:.1f}%")
    
    if tests_passed == total_tests:
        print("🎉 TODOS OS TESTES PASSARAM! Sistema funcionando perfeitamente!")
    else:
        print("⚠️  Alguns testes falharam. Verifique a implementação.")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)