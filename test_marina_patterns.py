def test_marina_patterns():
    # Mensagem da Marina  
    msg = "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final"
    
    low_orig = msg.lower()
    
    # Novos padrões de projeto
    projeto_patterns = [
        "projeto", "luminária", "luminaria", "ponto", "acrescentar", "iluminação", "iluminacao",
        "beiral", "gesso", "traçado", "layout", "porro", "garagem", "manter assim", "confirmar",
        "planta", "pd", "profundidade", "forro", "acabado", "final", "desenho", "perfis"
    ]
    
    projeto_match = [p for p in projeto_patterns if p in low_orig]
    
    print("=== TESTE NOVOS PADRÕES PROJETO ===")
    print(f"Mensagem: '{msg}'")
    print(f"Projeto patterns encontrados: {projeto_match}")
    
    if projeto_match:
        print("✅ Agora seria capturado como PROJETO")
        print("📝 Resposta esperada: 'Vou confirmar com a equipe responsável pelo projeto e te retorno com a validação'")
        print("🎯 Muito mais adequado que a saudação genérica!")
    else:
        print("❌ Ainda não seria capturado")
    
    # Testar também a mensagem do Bruno para garantir que também funciona
    bruno_msg = "Marquei com o Leo para ir na segunda instalar COnsegue os perfis e o desenho para amanhã??"
    bruno_low = bruno_msg.lower()
    bruno_match = [p for p in projeto_patterns if p in bruno_low]
    
    print(f"\n=== TESTE BRUNO (REGRESSÃO) ===")
    print(f"Bruno patterns: {bruno_match}")
    if bruno_match:
        print("✅ Bruno também seria capturado agora!")
    else:
        print("❌ Bruno ainda não seria capturado")

if __name__ == "__main__":
    test_marina_patterns()