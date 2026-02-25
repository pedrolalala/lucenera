import os
import sys
sys.path.insert(0, os.getcwd())

def analyze_bruno_humanization():
    # Mensagem do Bruno
    original_msg = "Marquei com o Leo para ir na segunda instalar COnsegue os perfis e o desenho para amanhã??"
    
    # Simular resposta robótica que chegaria aqui
    robotic_response = "Recebi sua mensagem e vou verificar"
    
    print("=== ANÁLISE DA HUMANIZAÇÃO ===")
    print(f"Mensagem original: '{original_msg}'")
    print(f"Resposta robótica: '{robotic_response}'")
    print()
    
    low_orig = original_msg.lower()
    
    # Testar padrões específicos
    print("=== TESTE DOS PADRÕES ===")
    
    # PROJETO/ILUMINAÇÃO
    projeto_patterns = [
        "projeto", "luminária", "luminaria", "ponto", "acrescentar", "iluminação", "iluminacao",
        "beiral", "gesso", "traçado", "layout", "porro", "garagem", "manter assim", "confirmar"
    ]
    projeto_match = [p for p in projeto_patterns if p in low_orig]
    print(f"Projeto patterns: {projeto_match}")
    
    # ESTOQUE/ENTREGA
    estoque_patterns = [
        "estoque", "retirar", "retirada", "pedindo", "itens", "já estão", "pendente",
        "restante", "frame", "conseguir", "disponível", "disponivel", "separar", "romaneio"
    ]
    estoque_match = [p for p in estoque_patterns if p in low_orig]
    print(f"Estoque patterns: {estoque_match}")
    
    # TÉCNICAS ESPECÍFICAS
    technical_patterns = [
        "watts?", "temperatura", "voltagem", "medida", "dimensão", "tamanho", 
        "cor?", "modelo", "marca", "especificação", "qual a", "lúmen", "lumens",
        "potência", "driver", "dimerizável", "rgb", "cct"
    ]
    technical_match = [p for p in technical_patterns if p in low_orig]
    print(f"Technical patterns: {technical_match}")
    
    # PREÇOS E PRAZOS
    price_patterns = [
        "preço", "preco", "valor", "custa", "quanto", "orçamento", "orcamento",
        "prazo", "entrega", "demora", "tempo", "quando", "desconto", "fornecedor"
    ]
    price_match = [p for p in price_patterns if p in low_orig]
    print(f"Price patterns: {price_match}")
    
    print()
    print("=== PALAVRAS CHAVE NA MENSAGEM ===")
    words = low_orig.split()
    print(f"Todas as palavras: {words}")
    
    # Identificar palavras específicas
    key_words = ["perfis", "desenho", "consegue", "amanhã", "instalar"]
    found_keys = [w for w in key_words if w in low_orig]
    print(f"Palavras-chave encontradas: {found_keys}")
    
    print()
    print("=== DIAGNÓSTICO ===")
    if estoque_match:
        print("✅ Deveria ter sido capturado por ESTOQUE patterns")
        print("📝 Resposta esperada: 'Vou verificar o status dos itens no estoque e te passo a atualização'")
    elif projeto_match:
        print("✅ Deveria ter sido capturado por PROJETO patterns") 
        print("📝 Resposta esperada: 'Vou confirmar com a equipe responsável pelo projeto e te retorno com a validação'")
    else:
        print("❌ NÃO foi capturado por nenhum padrão específico")
        print("🚨 Caiu no fallback genérico: 'Vou verificar e te retorno com as informações'")
        
        # Verificar no _generate_smart_fallback
        print("\n=== VERIFICAÇÃO SMART FALLBACK ===")
        if "consegue" in low_orig:
            print("🔍 Contém 'consegue' - mas não está nos padrões de humanização")
            print("💡 PROBLEMA: Palavra 'consegue' não está mapeada nos padrões!")

if __name__ == "__main__":
    analyze_bruno_humanization()