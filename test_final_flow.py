from main import is_finalizing_message

# Simular o novo fluxo
msg = 'Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton'
is_finalizer = is_finalizing_message(msg)

print('=== NOVO FLUXO COM PRIORIDADE ===')
print(f'Mensagem: "{msg}"')
print(f'is_finalizing_message: {is_finalizer}')

if is_finalizer:
    print('✅ Será detectado como FINALIZER na linha 3220!')
    print('✅ Status: ignored_finalizer')
else:
    print('❌ Ainda não está sendo detectado como finalizer')