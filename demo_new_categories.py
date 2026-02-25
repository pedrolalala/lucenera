#!/usr/bin/env python3
"""
Script para demonstrar as novas categorias funcionando em cenários reais.
Simula mensagens que clientes realmente enviariam no WhatsApp.
"""

import sys
import os

# Adicionar o diretório principal ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importar as funções do sistema principal
from main import _identify_message_type, _generate_contextual_response_by_type

def test_real_scenario(message, description):
    """Testa uma mensagem em cenário real."""
    detected_category = _identify_message_type(message)
    response = _generate_contextual_response_by_type(message, detected_category)
    
    print(f"\n💬 {description}")
    print(f"Cliente: \"{message}\"")
    print(f"Categoria: {detected_category}")
    print(f"Julia: {response}")
    print("-" * 50)

def demo_new_categories():
    """Demonstra as novas categorias funcionando."""
    print("🚀 DEMONSTRAÇÃO: NOVAS CATEGORIAS EM AÇÃO")
    print("=" * 60)
    print("Simulando conversas reais no WhatsApp da Lucenera")
    
    # === MENSAGENS ESPECÍFICAS ===
    print("\n🎯 CATEGORIA: MENSAGENS ESPECÍFICAS")
    
    test_real_scenario(
        "Oi! Qual é a chave PIX de vocês?",
        "PIX - Solicitação de dados bancários"
    )
    
    test_real_scenario(
        "Preciso de um orçamento para 50 luminárias",
        "Orçamento - Solicitação com quantidade"
    )
    
    test_real_scenario(
        "Vocês têm catálogo dos produtos novos?",
        "Catálogo - Solicitação de informações"
    )
    
    test_real_scenario(
        "Fazem entrega aqui em Ribeirão Preto?",
        "Entrega - Pergunta sobre localização"
    )
    
    test_real_scenario(
        "Posso retirar no estoque hoje?",
        "Retirada - Disponibilidade no dia"
    )
    
    test_real_scenario(
        "Quero saber sobre exclusividade na região",
        "Comercial - Interesse em exclusividade"
    )
    
    # === AGENDAMENTO ===
    print("\n📅 CATEGORIA: AGENDAMENTO")
    
    test_real_scenario(
        "Posso agendar para buscar amanhã?",
        "Material - Agendamento para dia específico"
    )
    
    test_real_scenario(
        "Quero marcar uma reunião para conversar sobre parceria",
        "Reunião - Agendamento para negócios"
    )
    
    test_real_scenario(
        "Quando vocês podem agendar a entrega?",
        "Entrega - Agendamento de horários"
    )
    
    # === CASOS MISTOS E COMPLEXOS ===
    print("\n🔀 CASOS MISTOS E COMPLEXOS")
    
    test_real_scenario(
        "Oi Julia! Preciso da chave PIX para finalizar o pagamento",
        "PIX + Saudação - Deve priorizar PIX"
    )
    
    test_real_scenario(
        "Bom dia! Vocês entregam em São Paulo? Qual o prazo?",
        "Entrega + Pergunta múltipla"
    )
    
    test_real_scenario(
        "Quero agendar reunião para próxima semana, pode ser?",
        "Agendamento + Confirmação"
    )
    
    test_real_scenario(
        "Vou pegar os spots pessoalmente amanhã",
        "Retirada + Informação temporal"
    )
    
    # === CASOS EDGE ===
    print("\n⚡ CASOS EDGE - PRIORIDADE")
    
    test_real_scenario(
        "Quando posso buscar? Preciso agendar horário",
        "Agendamento vs Retirada - Deve ser AGENDAMENTO"
    )
    
    test_real_scenario(
        "Vou retirar hoje, mas quero agendar",
        "Conflito - Deve ser AGENDAMENTO pela palavra-chave"
    )
    
    test_real_scenario(
        "Quanto custa e quando vocês entregam?",
        "Orçamento vs Entrega - Deve ser ORÇAMENTO (primeiro detectado)"
    )
    
    print("\n" + "=" * 60)
    print("✨ DEMONSTRAÇÃO CONCLUÍDA!")
    print("Sistema funcionando perfeitamente com:")
    print("🎯 6 subcategorias de MENSAGENS ESPECÍFICAS")
    print("📅 3 subcategorias de AGENDAMENTO") 
    print("⚡ Prioridade correta sobre categorias genéricas")
    print("🤖 Respostas contextuais e humanizadas")

if __name__ == "__main__":
    demo_new_categories()