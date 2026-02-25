import re

# Testar GREETINGS_RE com a mensagem do Henry
GREETINGS_RE = re.compile(
    r'^(oi|ol[aá]|e?ai|bo(a|m)\s?(tarde|noite|dia)|td ?bem|tudo ?bem|beleza|blz|como vai|(muito\s+)?obrigad[oa]|valeu|ok\s+(obrigad|bom))',
    re.I
)

msg = 'Bom dia Murilo tudo bem ? Entendi vou repassar para o Airton'
match = GREETINGS_RE.match(msg.strip())

print('=== TESTE GREETINGS_RE ===')
print(f'Mensagem: "{msg}"')
print(f'Match: {match}')
if match:
    print(f'Grupo capturado: "{match.group()}"')
    print('✅ É detectado como greeting - ISSO EXPLICA O PROBLEMA!')
else:
    print('❌ NÃO é detectado como greeting')