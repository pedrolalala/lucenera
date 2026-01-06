import os
from functools import lru_cache
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from openai import OpenAI

"""
Lucenera — Seleção de Persona
Versão: 2025-08
Decide a persona de resposta do bot com base em:
- ação prevista (quando já estimada pelo interpretador)
- sentimento da mensagem (positivo | neutro | negativo)
Personas: acolhedora | objetiva | tecnica | neutra
"""

# -----------------------------
# Config (lido quando necessário)
# -----------------------------
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.2"))

# -----------------------------
# Personas (diretrizes de tom)
# -----------------------------
PERSONAS: Dict[str, str] = {
    "acolhedora": (
        "Persona: Acolhedora — Tom empático, calmo e respeitoso. "
        "Acolha a frustração/ansiedade do cliente e indique o próximo passo objetivo. "
        "Frases curtas, sem exclamações e sem repetir o texto do cliente."
    ),
    "objetiva": (
        "Persona: Objetiva — Tom direto, focado em ação/validação (financeiro, entrega, agenda). "
        "Evite floreios; informe apenas o essencial."
    ),
    "tecnica": (
        "Persona: Técnica — Tom claro com termos de iluminação quando necessário, sem jargão pesado. "
        "Adequada para dúvidas de projeto/especificações."
    ),
    "neutra": (
        "Persona: Neutra — Cordial e informativa, ideal para confirmações simples."
    ),
}

# -----------------------------
# Cliente OpenAI (lazy)
# -----------------------------
@lru_cache(maxsize=1)
def _get_client() -> Optional[OpenAI]:
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

# -----------------------------
# Classificador de sentimento via LLM
# -----------------------------
_CLASSIFY_SYSTEM = (
    "Classifique o SENTIMENTO da mensagem do cliente como exatamente um destes rótulos: "
    "positivo | neutro | negativo. Responda apenas o rótulo em minúsculas."
)

def _classificar_sentimento_llm(texto: str) -> Tuple[str, float]:
    """
    Retorna (rotulo, confianca_aproximada).
    Se não houver client ou erro grave, assume 'neutro' como padrão.
    """
    client = _get_client()
    if client is None:
        return "neutro", 0.5

    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": texto or ""},
            ],
            temperature=TEMPERATURE,
        )
        rotulo = (resp.choices[0].message.content or "").strip().lower()
        if rotulo not in {"positivo", "neutro", "negativo"}:
            return "neutro", 0.5
        conf = 0.8 if rotulo != "neutro" else 0.7
        return rotulo, conf
    except Exception:
        return "neutro", 0.5

# -----------------------------
# Mapeamento: ação prevista -> persona
# -----------------------------
def _persona_por_acao(acao_prevista: Optional[str]) -> Optional[str]:
    if not acao_prevista:
        return None
    a = acao_prevista.strip().lower()
    if a == "reclamacao":
        return "acolhedora"
    if a in {"administracao", "agendamento_entrega_material"}:
        return "objetiva"
    if a == "projeto":
        return "tecnica"
    return None

# -----------------------------
# API principal
# -----------------------------
def selecionar_persona(
    mensagem_usuario: str,
    acao_prevista: Optional[str] = None,
) -> Tuple[str, Dict[str, float]]:
    """
    Decide a persona para a resposta curta do bot.
    Retorno:
        persona (str): {"acolhedora","objetiva","tecnica","neutra"}
        meta (dict): {"sentimento": <rotulo>, "confianca": <0..1>}
    """
    # 1) Ação prevista tem prioridade
    p = _persona_por_acao(acao_prevista)
    if p:
        sent, conf = _classificar_sentimento_llm(mensagem_usuario)
        return p, {"sentimento": sent, "confianca": conf}

    # 2) Sem ação prevista → usa sentimento
    sent, conf = _classificar_sentimento_llm(mensagem_usuario)
    persona = "acolhedora" if sent == "negativo" else "neutra"
    return persona, {"sentimento": sent, "confianca": conf}

def obter_texto_persona(persona: str) -> str:
    """Retorna o texto-diretriz da persona solicitada."""
    return PERSONAS.get(persona, PERSONAS["neutra"])

# -----------------------------
# Teste rápido
# -----------------------------
if __name__ == "__main__":
    casos = [
        ("chegou riscado, preciso trocar", "reclamacao"),
        ("segue comprovante de pagamento", "administracao"),
        ("qual a temperatura de cor do pendente do living?", "projeto"),
        ("boa tarde, tudo bem?", None),
    ]
    for msg, acao in casos:
        p, meta = selecionar_persona(msg, acao_prevista=acao)
        print(f"MSG: {msg}\n  acao_prevista={acao} -> persona={p} meta={meta}\n")
