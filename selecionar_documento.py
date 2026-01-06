# IMPORTS (stdlib → third-party → projeto)
import os
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from helpers import carrega

# ===== selecionar_documento.py =====

BASE_DIR = Path(__file__).resolve().parent
DADOS_DIR = BASE_DIR / "dados"
DADOS_TXT = DADOS_DIR / "dados_lucenera.txt"
POLITICAS_TXT = DADOS_DIR / "politicas_lucenera.txt"

# Carrega .env da raiz do projeto (mesma pasta do app.py)
load_dotenv(BASE_DIR / ".env")

def _clean_env(name: str) -> str | None:
    v = os.getenv(name)
    if v is None:
        return None
    return v.strip().strip('"').strip("'")

OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
OPENAI_MODEL = _clean_env("OPENAI_MODEL") or "gpt-4o-mini"

# Cliente OpenAI (pode ficar None se não houver chave)
_client: OpenAI | None = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# Carrega contextos locais
dados_lucenera = carrega(str(DADOS_TXT))
politicas_lucenera = carrega(str(POLITICAS_TXT))

if not dados_lucenera:
    print("[selecionar_documento] Aviso: dados_lucenera.txt não encontrado ou vazio.")
if not politicas_lucenera:
    print("[selecionar_documento] Aviso: politicas_lucenera.txt não encontrado ou vazio.")

def selecionar_documento(chave: str) -> str:
    """Retorna o texto de contexto a ser injetado na conversa, baseado no rótulo."""
    k = (chave or "").strip().lower()
    if "politica" in k:
        return (dados_lucenera or "") + "\n\n" + (politicas_lucenera or "")
    if "produto" in k:
        instru = (
            "\n\n[CONTEXTOS DE PRODUTOS]\n"
            "- Para disponibilidade e preço de venda, utilize as FERRAMENTAS do assistente "
            "(consulta ao Excel dados/produtos.xlsx via functions). "
            "Não responder com custo, marca, fornecedor, NCM ou impostos.\n"
        )
        return (dados_lucenera or "") + instru
    return dados_lucenera or ""

def selecionar_contexto(mensagem_usuario: str) -> Literal["dados", "politicas", "produtos"]:
    """
    Usa OpenAI para classificar a mensagem do usuário.
    Em caso de falha total, assume 'dados' como contexto padrão.
    """
    if not _client or not OPENAI_API_KEY:
        print("[selecionar_documento] OpenAI client ausente. Usando contexto 'dados' por padrão.")
        return "dados"

    prompt_sistema = (
        "Classifique a mensagem retornando exatamente um dos rótulos: dados | politicas | produtos.\n\n"
        "- dados: informações institucionais, localização, contatos, redes sociais.\n"
        "- politicas: regras de compra, prazos, trocas, devoluções, garantia, formas de pagamento.\n"
        "- produtos: dúvidas sobre preço, disponibilidade, código, estoque, etc.\n\n"
        "Responda apenas com um dos três rótulos, sem explicação adicional."
    )

    try:
        resp = _client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": mensagem_usuario or ""},
            ],
            temperature=0,
            max_tokens=10,
        )
        rotulo = (resp.choices[0].message.content or "").strip().lower()
        if rotulo in {"dados", "politicas", "produtos"}:
            return rotulo
        print(f"[selecionar_documento] Classificação inválida recebida: {rotulo!r}")
        return "dados"  # fallback seguro, mas não heurístico
    except Exception as e:
        print(f"[selecionar_documento] Erro ao classificar contexto via OpenAI: {e}")
        return "dados"
