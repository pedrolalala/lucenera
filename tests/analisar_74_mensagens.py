#!/usr/bin/env python3
"""
Script para testar todas as 74 mensagens reais de clientes
e verificar como o sistema de respostas automáticas se comporta.
"""

import sys
import os

# Adicionar o diretório principal ao path
sys.path.insert(0, os.path.dirname(__file__))

# Importar as funções do sistema principal
from main import _identify_message_type, _generate_contextual_response_by_type

# Todas as 74 mensagens de teste
MENSAGENS_TESTE = [
    "Oi Murilo!!! Bom dia!",
    "LUC91 - SPOT GERRY COM ARTICULACAO - GU10 – BRANCO – 6 UNIDADES Quantos watts? E qual a temperatura de cor?",
    "País, bom dia, tudo bem? Demorei a responder que eu tava viajando, viu? Hoje que eu tô pondo a casa em ordem aqui. Inclusive, eu tô aqui na obra e... o Eliel, que é encarregado aqui da elétrica, ele me falou um detalhe aqui, vê se a gente faz alguma coisa ou deixa assim mesmo. Vou te mandar pelo projeto aqui, pra você entender.",
    "bom dia, tudo bem? lá no começo de dezembro vocês comentaram que já estavam pedindo todos os itens de iluminação… já estão com vocês? queria saber se consigo retirar sei que estava pendente aquela questão dos itens no frame, mas o restante estava ok né…",
    "a entrada da garagem onde eu fiz o traçado em vermelho o quadrado em vermelho o retângulo em vermelho é o beiral da entrada garagem nesse beiral tá constando porro de gesso e não tem luminária aí vai manter assim mesmo né e nessa parte de trás nesse outro retângulo aí que também é uma parte que não tem nada de iluminação é só para confirmar porque o projeto o projeto tá tá vindo para cá amanhã se tiver que acrescentar algum ponto aqui ainda dá tempo mas por manter assim manter assim também tá tudo certo beleza",
    "Ok obrigado, bom dia",
    "Tudo também! Eles já instalaram o forro de gesso e vão começar a instalação do vinílico.",
    "Acredito que sim! O Guto Cyrino que está tocando essa parte, posso te pedir a gentileza de falar com ele diretamente sobre isso Murillo?",
    "Ele até está falando com alguém daí, mas não sei com quem é!",
    "Murilo?",
    "Oi bom dia Tá OK",
    "A L14 e a L15 é aquela que eu tenho aqui, né? Que vocês mandaram uma amostra.",
    "Magina",
    "Eu estou na obra",
    "Eu aguardo Muito obrigada",
    "O Murilo, eu lembro, inclusive tá com o Guto, essa amostra que eu deixei com eles lá mesmo. Eu acredito que tá tudo certo da L14 e da L15. O L14 é o mesmo, né? A única coisa que ele ia ser instalado no Fujitsu, então ok, não teria problema, mas é mais para a questão da L15. Eu só tô realmente esperando ele me confirmar isso, mas o importante é que ele tem a amostra em mãos, então fica mais tranquilo, porque ele tá adiando isso com o pessoal que vai instalar o vinílico.",
    "Me envia à distância dos spots L1",
    "A da academia e a do corredor, acho que você pode sim já confirmar o tamanho para já produzir, porque não vamos mudar, e é forro de gesso normal, e aí segura só a L15 mesmo, mas aí confirma com o guto da L15 que eu acredito que vai dar certo, e aí é só realmente pegar a medida para produzir também com ele.",
    "bom dia, vou verificar com o engenheiro",
    "Perfeito",
    "Obrigada, Murilo Como você faz esse valor?",
    "Murilo, fechamos 12 mil em 4x?",
    "Olá, bom dia Tudo bem ?",
    "Em 3x então",
    "É só mesmo por encomenda agora, e aí o prazo de importação, a previsão é no mínimo 180 dias, tá?",
    "Eu que agradeço Aguardo",
    "Claro",
    "Há sim Vou deixar cabo com folga para movê los Obrigado",
    "Ok, obrigado",
    "Oi pessoal, boa tarde, tudo bem? Deixa eu fazer uma pergunta, como é que tá o material das telas lá do Alexandre, acho que Alexandre Tuzzi, né? Tô perguntando porque a Roberta pediu pra gente se organizar de fazer a instalação, aí eu queria que vocês me dessem um retorno pra que eu veja e dê uma posição pra ela de quando que a gente poderia ir.",
    "Luísa Soares de Almeida Marin. 359.730.258-02. 43.453.889-9. 01240-001. Rua Maranhão 391, Higienópolis São Paulo Telefone (16) 99791-0407. luisasamarin30@gmail.com",
    "Boa tarde",
    "Murilo, só me confirma uma coisa, é muito importante aqui, principalmente que eu tô em São Paulo. Quando é que você consegue me entregar? O Bruno falou que talvez até traga pra cá. Quando é que essas mercadorias estarão disponíveis aí pra retirada, por favor? Pra eu me alinhar, inclusive, com a mão de obra aqui em São Paulo.",
    "certo!! melhor trabalharmos com 20 dias",
    "Boa tarde tudo bem ?",
    "Ola boa tarde",
    "Por favor , poderia entrar em contato com o arquiteto Marcelo Pânico que está cuidando da obra , para organizar instalação do espelho e iluminação ?",
    "Fernanda me retornou que esta tudo certo, ja foi feito o cadastro e ja recebemos a documentação Agora estamos aguardando o financeiro retornar O nosso financeiro aprovar A Fernanda esta informando tudo sobre o processo por e-mail",
    "Tem mais algum material que ficou com vocês e entrega está pendente , por favor ?",
    "20 dias úteis, Murilo?",
    "Boa tarde, bem e você? Pode sim, já serão instaladas?",
    "Bom dia Murillo. Bem e vc? Não foi feito a pintura, mas acho que as medidas da certo de tirar.",
    "Bom dia!",
    "Thais, consegue confirmar se foram entregues?",
    "Os materiais ja estão todos na obra? • Fitas de led • Fontes • Perfis das tela",
    "Marquei com o Leo para ir na segunda instalar COnsegue os perfis e o desenho para amanhã??",
    "Sim, a lona só depois da marcenaria, mas ele já vai instalar os perfis e led Esse material",
    "Bom dia, Thais. Isabela aqui, tudo bem? Desculpe a demora em retornar, no caso, esse é o spot de 65mm, correto? Iremos encaminhar para os clientes Teriam imagens tambem do spot com frame previsto para a área do escritório? Como ele fica no forro de madeira",
    "Bom dia",
    "Ótimo! O eletricista vai estar na obra na parte da manhã, e o resto do dia estará o pessoal da marcenaria",
    "tudo bem também, thaís",
    "Okk obrigado",
    "Pode deixar",
    "Sim, só um minuto",
    "Sim",
    "Bruno, essa tela, elas são dois retornos que precisa pra ela, tá? O C40 e o C41. O C40 vai fazer a iluminação de fundo da tela e o C41 faz a iluminação dimerizável. Inclusive, um dos retornos, ele tem que colocar um dimmer lá pra nossa.",
    "Bye. Bye.",
    "Bom dia tudo bem? Chegou a retirar tudo que precisava nesse dia? Faltou algo?",
    "A disposição",
    "Thais bom dia! Tudo bem?",
    "Acredito que o Fabrício não tenha entrado na sala de reunião ele está em uma apresentação Você consegue aguardar?",
    "Oi Helena, tudo ótimo Que bom que deu certo",
    "Bom dia! Tudo bem e você. Saiu sim.",
    "Você precisava de quantas peças?",
    "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: O PD acabado vou te mandar a planta de forro final",
    "Boa tarde! Tudo bem? Me perdoe as mensagens desceram e esqueci de ter retornar A profundidade que voce perguntou: 47cm O PD acabado vou te mandar a planta de forro final",
    "Quantas peças você precisa?",
    "Concretagem Concluída 🙏",
    "Obrigado!",
    "Quando vocês atualizarem, me manda pra eu mandar pra Automundi?",
    "Pergunto caso queiram encaminhar alguma outra referencia",
    "Isso, a questão seria o rasgo aberto ou acrílico",
    "Boa tarde Conseguiram finalizar o projeto?",
    "Tb não recebi os boletos"
]

def analisar_mensagem(num, mensagem):
    """Analisa uma mensagem e retorna os resultados."""
    categoria = _identify_message_type(mensagem)
    resposta = _generate_contextual_response_by_type(mensagem, categoria)
    
    return categoria, resposta

def executar_analise_completa():
    """Executa análise completa de todas as mensagens."""
    print("🔍 ANÁLISE COMPLETA: 74 MENSAGENS REAIS DE CLIENTES")
    print("=" * 80)
    
    # Contadores de categorias
    contadores = {}
    
    for i, mensagem in enumerate(MENSAGENS_TESTE, 1):
        categoria, resposta = analisar_mensagem(i, mensagem)
        
        # Contar categorias
        contadores[categoria] = contadores.get(categoria, 0) + 1
        
        # Exibir resultado
        print(f"\n📝 MENSAGEM {i:02d}")
        print(f"Cliente: \"{mensagem[:80]}{'...' if len(mensagem) > 80 else ''}\"")
        print(f"Categoria: {categoria}")
        print(f"Julia: {resposta}")
        print("-" * 60)
    
    # Estatísticas finais
    print("\n" + "=" * 80)
    print("📊 ESTATÍSTICAS FINAIS")
    print(f"Total de mensagens analisadas: {len(MENSAGENS_TESTE)}")
    print("\nDistribuição por categoria:")
    
    for categoria, count in sorted(contadores.items()):
        porcentagem = (count / len(MENSAGENS_TESTE)) * 100
        print(f"  {categoria}: {count} mensagens ({porcentagem:.1f}%)")
    
    print("\n🎯 ANÁLISE DE PERFORMANCE:")
    
    # Calcular performance das novas categorias
    novas_categorias = ['mensagem_especifica', 'agendamento']
    total_novas = sum(contadores.get(cat, 0) for cat in novas_categorias)
    
    print(f"Novas categorias detectadas: {total_novas} mensagens ({(total_novas/len(MENSAGENS_TESTE))*100:.1f}%)")
    print(f"Categorias existentes: {len(MENSAGENS_TESTE) - total_novas} mensagens ({((len(MENSAGENS_TESTE) - total_novas)/len(MENSAGENS_TESTE))*100:.1f}%)")
    
    return contadores

if __name__ == "__main__":
    contadores = executar_analise_completa()