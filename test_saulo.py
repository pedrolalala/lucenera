from main import is_finalizing_message

# Testar a mensagem do Saulo
msg = 'Pode deixar'
result = is_finalizing_message(msg)

print('=== TESTE SAULO PIAZZA ===')
print(f'Mensagem: "{msg}"')
print(f'is_finalizing_message: {result}')

if result:
    print('✅ Deveria ser ignored_finalizer')
else:
    print('❌ Por isso está gerando resposta de IA')
    print('🚨 PROBLEMA: "Pode deixar" não está sendo detectado como finalizer')