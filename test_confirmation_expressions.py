from main import is_finalizing_message

# Testar várias expressões de confirmação/autorização
test_cases = [
    "Pode deixar",
    "pode sim", 
    "pode ir",
    "ta liberado",
    "tá liberado",
    "autorizo",
    "autorizado",
    "Pode deixar assim",
    "Ok pode deixar",
    "Perfeito, pode deixar"
]

print('=== TESTE EXPRESSÕES DE CONFIRMAÇÃO ===')
for msg in test_cases:
    result = is_finalizing_message(msg)
    status = "✅ ignored_finalizer" if result else "❌ vai gerar AI"
    print(f'"{msg:<25}" -> {status}')