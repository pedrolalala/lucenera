#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste das mensagens da Luísa"""

from services.chatgpt_responder import _gerar_resposta_impl, _classify_short_message

# Testar as 3 mensagens da Luísa
messages = [
    'Sim!',
    'Está ótimo dessa maneira', 
    '20/02 20/03 é 20/04'
]

print('=== TESTE MENSAGENS LUÍSA ===')
for i, msg in enumerate(messages, 1):
    print(f'\n{i}. Mensagem: "{msg}"')
    
    # Classificação
    classification = _classify_short_message(msg)
    print(f'   Classificação: {classification}')
    
    # Resposta gerada
    try:
        resposta = _gerar_resposta_impl(msg, f'phone:test{i}', mensagem_id=i, telefone=f'test{i}')
        print(f'   Resposta: {resposta[:100]}...')
        
        if '[SEM RESPOSTA NECESSÁRIA]' in resposta:
            print('   Status: ✅ Sem resposta (correto)')
        else:
            print('   Status: ⚠️  Gerando resposta')
            
    except Exception as e:
        print(f'   Erro: {e}')