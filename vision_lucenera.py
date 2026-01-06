# IMPORTS (stdlib → third-party → projeto)
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from helpers import imagem_data_url

# ===== vision_lucenera.py =====

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def analisar_imagem(path: str, prompt: str = "Descreva a imagem com foco em iluminação e ambiente."):
    """
    Envia a imagem (como data URL) para o modelo com visão e retorna o texto gerado.
    """
    if _client is None:
        return "Não foi possível analisar a imagem (OPENAI_API_KEY ausente)."

    data_url = imagem_data_url(path)

    # Enviar a instrução + URL como string, evitando estrutura de objetos no 'content'.
    message_text = f"{prompt}\nURL: {data_url}"
    resp = _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": message_text}],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()
