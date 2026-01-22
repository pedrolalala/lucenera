# -*- coding: utf-8 -*-
"""
assistente_lucenera.py — Assistants v2 (compat)
- Cria Vector Store com os TXT da Lucenera (quando disponíveis)
- Cria Assistant com file_search + suas function tools
- Persiste {assistant_id, thread_id, vector_store_id} em assistente_lucenera.json
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

# Tools do projeto (se existirem)
try:
    from tools_lucenera import minhas_tools  # type: ignore
except Exception:
    minhas_tools = []

# -----------------------------
# Paths / ENV
# -----------------------------
BASE_DIR: Path = Path(__file__).resolve().parent
DADOS_DIR: Path = BASE_DIR / "dados"
DADOS_DIR.mkdir(parents=True, exist_ok=True)

DADOS_TXT: Path = DADOS_DIR / "dados_lucenera.txt"
POLITICAS_TXT: Path = DADOS_DIR / "politicas_lucenera.txt"
ASSISTENTE_JSON: Path = BASE_DIR / "assistente_lucenera.json"

load_dotenv(BASE_DIR / ".env")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY não encontrado. Crie .env com, por exemplo:\n"
        'OPENAI_API_KEY="sk-..."'
    )

_client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------------
# Helpers SDK compat
# -----------------------------
def _get_vs_namespace():
    beta = getattr(_client, "beta", None)
    if beta is not None and hasattr(beta, "vector_stores"):
        return beta.vector_stores
    if hasattr(_client, "vector_stores"):
        return _client.vector_stores
    return None

def _get_file_batches(ns) -> Optional[object]:
    return getattr(ns, "file_batches", None)

# -----------------------------
# Upload de arquivos
# -----------------------------
def _existing_files() -> list[Path]:
    files: list[Path] = []
    for p in (DADOS_TXT, POLITICAS_TXT):
        if p.exists():
            files.append(p)
        else:
            print(f"[assistente_lucenera] Aviso: arquivo não encontrado: {p.name}")
    return files

def _criar_vector_store_com_arquivos(paths: list[Path]) -> Optional[str]:
    vs_api = _get_vs_namespace()
    if vs_api is None:
        print("[assistente_lucenera] AVISO: SDK sem suporte a vector_stores. Ignorando file_search.")
        return None

    vs = vs_api.create(name="Lucenera Base v1")

    if paths:
        file_batches = _get_file_batches(vs_api)
        if file_batches is None:
            print("[assistente_lucenera] SDK sem suporte a 'file_batches'; vector store criado vazio.")
        else:
            file_objs = [open(p, "rb") for p in paths]
            try:
                file_batches.upload_and_poll(
                    vector_store_id=vs.id,
                    files=file_objs,
                )
                nomes = ", ".join(p.name for p in paths)
                print(f"[assistente_lucenera] Vector Store criado: {vs.id} (arquivos: {nomes})")
            finally:
                for f in file_objs:
                    try:
                        f.close()
                    except Exception:
                        pass
    else:
        print("[assistente_lucenera] Nenhum arquivo disponível. Vector Store criado vazio.")

    return vs.id

# -----------------------------
# Criação do Assistant e Thread
# -----------------------------
def criar_thread():
    return _client.beta.threads.create()

def criar_assistente(vector_store_id: Optional[str]):
    instrucoes = ( 
        "Você é Julia, assistente virtual da Thais, e responde mensagens do WhatsApp da Thais em português do Brasil.\n\n"

        "IDENTIDADE:\n"
        "- Nunca diga que é IA, robô ou mencione sistemas, APIs ou código.\n"
        "- Sempre se apresente como 'Julia, assistente da Thais'.\n"
        "- O início da resposta deve SEMPRE ser no formato '*Julia:* ' seguido do texto no mesmo parágrafo.\n\n"

        "ESTILO:\n"
        "- Use frases curtas, linguagem simples e clara.\n"
        "- Não repita a pergunta do cliente nem use exclamações.\n"
        "- Nunca mencione o nome do cliente na resposta.\n"
        "- Evite frases genéricas como 'vou verificar os detalhes' se a mensagem do cliente não contiver pedido explícito.\n"
        "- Para saudações, cortesia, agradecimentos ou mensagens de atualização, responda de forma natural e simpática, mantendo o tom humano.\n\n"

        "REGRAS DE NEGÓCIO:\n"
        "- Para dados institucionais ou políticas, use apenas o conteúdo dos arquivos disponíveis (file_search).\n"
        "- Para preço, estoque e informações de produto, utilize as FERRAMENTAS integradas (functions).\n"
        "- Nunca mencione custo, marca, fornecedor, NCM, impostos ou margem de lucro.\n"
        "- Se não tiver certeza sobre algo técnico, de preço ou produto, diga que vai verificar com a Thais e retornar.\n\n"

        "EXEMPLOS DE TOM E CONTEXTO:\n"
        "  • Cliente: 'Oii, tudo sim e você?' → Julia: 'Tudo ótimo sim, obrigada por perguntar.'\n"
        "  • Cliente: 'Obrigada por avisar. Ele já está a caminho.' → Julia: 'Obrigada por avisar.'\n"
        "  • Cliente: 'Perfeito, combinado então.' → Julia: 'Combinado, obrigada!'\n"
        "  • Cliente: 'Bom dia!' → Julia: 'Bom dia! '\n"
        "  • Cliente: 'Tudo certo por aí?' → Julia: 'Tudo certo sim, e por aí?'\n"

        "IDENTIDADE:\n"
        "- Nunca diga que é IA, robô ou mencione sistemas, APIs ou código.\n"
        "- Sempre se apresente como 'Julia, assistente da Thais'.\n"
        "- O início da resposta deve SEMPRE ser no formato '*Julia:* ' seguido do texto no mesmo parágrafo.\n\n"
         ) 


    tools = list(minhas_tools)
    tool_resources = {}

    if vector_store_id:
        tools.append({"type": "file_search"})
        tool_resources = {"file_search": {"vector_store_ids": [vector_store_id]}}

    return _client.beta.assistants.create(
        name="Atendente Lucenera",
        instructions=instrucoes,
        model=OPENAI_MODEL,
        tools=tools,
        tool_resources=tool_resources or None,
    )

# -----------------------------
# API pública principal
# -----------------------------
def pegar_json() -> dict:
    """
    Retorna { assistant_id, thread_id, vector_store_id }.
    Se não existir ainda, cria tudo e salva em assistente_lucenera.json.
    """
    if not ASSISTENTE_JSON.exists():
        files = _existing_files()
        vs_id = _criar_vector_store_com_arquivos(files)
        assistant = criar_assistente(vs_id)
        thread = criar_thread()
        data = {
            "assistant_id": assistant.id,
            "thread_id": thread.id,
            "vector_store_id": vs_id,
        }
        with open(ASSISTENTE_JSON, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        print(f"[assistente_lucenera] Assistente criado e salvo em {ASSISTENTE_JSON.name}")

    with open(ASSISTENTE_JSON, "r", encoding="utf-8") as f:
        return json.load(f)
    