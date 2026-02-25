# REMOVIDO: Análise de imagem desabilitada conforme solicitação
# Este arquivo não é mais usado no fluxo principal
# O sistema agora usa apenas respostas padronizadas para imagens/vídeos/documentos

# -*- ARQUIVO DESABILITADO -*-
"""
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
    # FUNÇÃO DESABILITADA - agora usa resposta padronizada
    return "Análise de imagem desabilitada. Use resposta padronizada."
"""
