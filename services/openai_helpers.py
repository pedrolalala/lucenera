# -*- coding: utf-8 -*-
# services/openai_helpers.py
# Utilitários de integração com OpenAI (Assistants v2) + helpers de formatação.
# Agora inclui o pré-processamento de mídia (áudio / imagem / vídeo).

from __future__ import annotations

import os
import time
import io         # <- PATCH: mídia
import re         # <- PATCH: mídia
import mimetypes  # <- PATCH: mídia
import requests   # <- PATCH: mídia
from typing import Callable, Iterable, List, Optional, Tuple, Dict, Any
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
from openai import OpenAI

# -------------------------------------------------------------------
# Carrega .env AQUI também (robustez)
# -------------------------------------------------------------------
# 1) tenta localizar automaticamente (walk-up)
_env_path = find_dotenv()
if not _env_path:
    # 2) tenta projeto/../.env (ex.: .../lucenera/.env)
    _candidate = Path(__file__).resolve().parents[1] / ".env"
    if _candidate.exists():
        _env_path = str(_candidate)
    else:
        # 3) tenta CWD/.env
        _candidate = Path.cwd() / ".env"
        if _candidate.exists():
            _env_path = str(_candidate)

if _env_path:
    load_dotenv(_env_path)

# -------------------------------------------------------------------
# ENV helpers
# -------------------------------------------------------------------
def _clean_env(name: str) -> Optional[str]:
    v = os.getenv(name)
    if v is None:
        return None
    return v.strip().strip('"').strip("'") or None

OPENAI_API_KEY = _clean_env("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Defina OPENAI_API_KEY no arquivo .env (ou exporte a env antes de iniciar o app).")

OPENAI_MODEL = _clean_env("OPENAI_MODEL") or "gpt-4o-mini"
OPENAI_ORG = _clean_env("OPENAI_ORG")            # opcional
OPENAI_BASE_URL = _clean_env("OPENAI_BASE_URL")  # opcional

# -------------------------------------------------------------------
# Cliente e Modelo
# -------------------------------------------------------------------
_client_kwargs: Dict[str, Any] = {"api_key": OPENAI_API_KEY}
if OPENAI_ORG:
    _client_kwargs["organization"] = OPENAI_ORG
if OPENAI_BASE_URL:
    _client_kwargs["base_url"] = OPENAI_BASE_URL

cliente = OpenAI(**_client_kwargs)
modelo = OPENAI_MODEL

# -------------------------------------------------------------------
# Constantes de status
# -------------------------------------------------------------------
STATUS_COMPLETED = "completed"
STATUS_REQUIRES_ACTION = "requires_action"
STATUS_TERMINO_FALHA = {"failed", "cancelled", "expired", "incomplete"}
STATUS_EM_ANDAMENTO = {"queued", "in_progress", "cancelling"}

# -------------------------------------------------------------------
# Helpers de mensagens/threads
# -------------------------------------------------------------------
def _coletar_textos_do_conteudo(content: Iterable[Any]) -> List[str]:
    """Coleta todos os blocos de texto de uma mensagem do Assistant."""
    textos: List[str] = []
    for c in content or []:
        if getattr(c, "type", None) == "text":
            t = getattr(getattr(c, "text", None), "value", "") or ""
            if t:
                textos.append(t)
    return textos

def _extrair_ultimo_texto_da_thread(thread_id: str, buscar_limite: int = 10) -> str:
    """Retorna o texto da mensagem mais recente do 'assistant' na thread."""
    msgs = cliente.beta.threads.messages.list(thread_id=thread_id, limit=buscar_limite, order="desc")
    for m in getattr(msgs, "data", []) or []:
        if getattr(m, "role", None) != "assistant":
            continue
        textos = _coletar_textos_do_conteudo(getattr(m, "content", []) or [])
        if textos:
            return "\n".join([t.strip() for t in textos if t.strip()])
    return ""

def _run_error_humanizado(run_obj: Any) -> str:
    """Mensagem de erro amigável a partir do objeto run."""
    last_err = getattr(run_obj, "last_error", None)
    if last_err:
        code = getattr(last_err, "code", None) or "-"
        msg = getattr(last_err, "message", None) or "erro sem mensagem"
        return f"{code}: {msg}"
    return f"status={getattr(run_obj, 'status', 'desconhecido')}"

# -------------------------------------------------------------------
# Aguardar execução (run)
# -------------------------------------------------------------------
def aguardar_run(
    thread_id: str,
    run: Any,
    timeout_s: int = 90,
    poll_interval_s: float = 0.8,
    on_requires_action: Optional[Callable[[Any], List[Dict[str, str]]]] = None,
) -> str:
    """
    Faz polling do run até concluir.
    - Em 'requires_action', se 'on_requires_action' for fornecido, chama o handler,
      envia os tool_outputs e continua. Caso contrário, retorna "" para o chamador tratar.
    - Em falha/timeout, levanta exceção com diagnóstico.
    - Em sucesso, retorna o último texto do assistente na thread.
    """
    inicio = time.monotonic()
    run_id = getattr(run, "id", None)

    while True:
        run = cliente.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        status = getattr(run, "status", None)

        if status == STATUS_COMPLETED:
            return _extrair_ultimo_texto_da_thread(thread_id)

        if status == STATUS_REQUIRES_ACTION:
            if on_requires_action is not None:
                tool_outputs = on_requires_action(run) or []
                if tool_outputs:
                    cliente.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread_id,
                        run_id=run_id,
                        tool_outputs=tool_outputs,
                    )
                else:
                    return ""
            else:
                return ""

        if status in STATUS_TERMINO_FALHA:
            detalhe = _run_error_humanizado(run)
            raise RuntimeError(f"Execução terminou com status '{status}'. Detalhe: {detalhe}")

        if (time.monotonic() - inicio) > timeout_s:
            raise TimeoutError(f"Run {run_id} não concluiu em {timeout_s}s (status atual: {status}).")

        time.sleep(poll_interval_s)

# -------------------------------------------------------------------
# Helpers de formatação de resposta
# -------------------------------------------------------------------
def _ensure_prefix(texto: str, prefixo: str = "Julia.") -> str:
    """
    Garante que toda resposta comece com o prefixo (ex: "Julia.") em linha separada.
    Mesmo que o modelo não responda nada, ainda retorna o prefixo.
    """
    corpo = (texto or "").strip()

    # Sempre começa com o prefixo, mesmo se estiver vazio
    if not corpo:
        return f"{prefixo}\n..."  # ou coloque o fallback desejado aqui

    # Se já começa com o prefixo, evita duplicar
    linhas = [l.rstrip() for l in corpo.splitlines()]
    if linhas and linhas[0].strip().lower().startswith(prefixo.lower()):
        resto = "\n".join(linhas[1:]).strip()
        return f"{prefixo}\n{resto}" if resto else f"{prefixo}\n"

    return f"{prefixo}\n{corpo}"


# -------------------------------------------------------------------
# Atalho: criar run e aguardar
# -------------------------------------------------------------------
def executar_assistente_e_aguardar(
    assistant_id: str,
    thread_id: str,
    *,
    instructions: Optional[str] = None,
    timeout_s: int = 90,
    on_requires_action: Optional[Callable[[Any], List[Dict[str, str]]]] = None,
) -> str:
    """Cria o run para um assistant/thread e aguarda a conclusão, retornando o último texto do assistente."""
    run = cliente.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
        instructions=instructions,
    )
    return aguardar_run(
        thread_id=thread_id,
        run=run,
        timeout_s=timeout_s,
        on_requires_action=on_requires_action,
    )

# ===================================================================
# ===================  PRÉ-PROCESSAMENTO DE MÍDIA  ==================
# ===================================================================
# Objetivo: transformar áudio/vídeo em texto (transcrição) e gerar descrição
# curta para imagem. O resultado substitui row['mensagem']['text'] para que
# o Assistente responda com base no conteúdo já interpretado.

# Configuráveis via .env
MAX_MEDIA_BYTES = int(os.getenv("MAX_MEDIA_BYTES") or 25_000_000)  # 25 MB
TRANSCRIBE_MODEL = os.getenv("TRANSCRIBE_MODEL") or "whisper-1"    # fallback tenta "gpt-4o-transcribe"
VISION_MODEL = os.getenv("VISION_MODEL") or "gpt-4o-mini"

def _get_url_from_bracket_text(text: str) -> Optional[str]:
    """
    Extrai a primeira URL de um texto padronizado, p.ex.:
    "[Áudio recebido: https://... .ogg]"
    """
    if not isinstance(text, str):
        return None
    m = re.search(r"https?://[^\]\s]+", text)
    return m.group(0) if m else None

def _download(url: str) -> Optional[bytes]:
    """Baixa o conteúdo binário, com limite de tamanho."""
    try:
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        b = r.content
        if len(b) > MAX_MEDIA_BYTES:
            return None
        return b
    except Exception:
        return None

def _transcribe_bytes(data: bytes, filename: str = "audio.webm") -> Optional[str]:
    """
    Transcreve bytes de áudio/vídeo usando Whisper (whisper-1).
    Se falhar, tenta 'gpt-4o-transcribe'.
    """
    # 1ª tentativa
    try:
        buf = io.BytesIO(data); buf.name = filename
        resp = cliente.audio.transcriptions.create(model=TRANSCRIBE_MODEL, file=buf)
        txt = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
        return (txt or "").strip() or None
    except Exception:
        pass
    # fallback
    try:
        buf = io.BytesIO(data); buf.name = filename
        resp = cliente.audio.transcriptions.create(model="gpt-4o-transcribe", file=buf)
        txt = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else None)
        return (txt or "").strip() or None
    except Exception:
        return None

def _image_caption(url: str) -> Optional[str]:
    """
    Gera uma descrição objetiva (1–2 frases) para imagem usando GPT-4o-mini com visão.
    """
    # Prefer using the project's vision helper which accepts a local file path.
    try:
        from vision_lucenera import analisar_imagem
    except Exception:
        analisar_imagem = None

    # 1) If we have the project's vision helper, try download -> local file -> analyze
    if analisar_imagem:
        try:
            import tempfile
            # download image bytes
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                # guess extension from Content-Type or url
                ctype = resp.headers.get('Content-Type', '')
                ext = mimetypes.guess_extension(ctype.split(';')[0].strip() or '') or Path(url).suffix or '.jpg'
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
                    tf.write(resp.content)
                    tmp_path = tf.name
                try:
                    cap = analisar_imagem(tmp_path)
                    return (cap or '').strip() or None
                finally:
                    try:
                        Path(tmp_path).unlink()
                    except Exception:
                        pass
        except Exception:
            # fall through to best-effort cloud call below
            pass

    # 2) Fallback: ask the model directly with the URL (legacy behaviour)
    try:
        prompt = (
            "Descreva objetivamente a imagem (1–2 frases úteis para atendimento técnico/comercial no WhatsApp)."
            f"\nURL: {url}"
        )
        msgs = [{"role": "user", "content": prompt}]
        out = cliente.chat.completions.create(model=VISION_MODEL, messages=msgs, temperature=0.2)
        cap = (out.choices or [])[0].message.content
        return (cap or "").strip() or None
    except Exception:
        return None

def _detect_media_urls_from_row(row: dict) -> Dict[str, Optional[str]]:
    """
    Tenta achar URLs de áudio/imagem/vídeo em:
      - row['mensagem']['raw'] (padrões Z-API: audio.audioUrl, image.imageUrl/thumbnailUrl, video.videoUrl)
      - texto padronizado com colchetes: "[Áudio recebido: URL]", "[Imagem recebida: URL]", "[Vídeo recebido: URL]"
    """
    msg = (row.get("mensagem") or {})
    raw = msg.get("raw") or {}
    text = (msg.get("text") or "").strip()

    audio_url = image_url = video_url = None

    if isinstance(raw, dict):
        aud = raw.get("audio")
        if isinstance(aud, dict):
            audio_url = aud.get("audioUrl") or audio_url
        img = raw.get("image")
        if isinstance(img, dict):
            image_url = img.get("imageUrl") or img.get("thumbnailUrl") or image_url
        vid = raw.get("video")
        if isinstance(vid, dict):
            video_url = vid.get("videoUrl") or video_url

    if not audio_url and text.startswith("[Áudio recebido:"):
        audio_url = _get_url_from_bracket_text(text)
    if not image_url and text.startswith("[Imagem recebida:"):
        image_url = _get_url_from_bracket_text(text)
    if not video_url and text.startswith("[Vídeo recebido:"):
        video_url = _get_url_from_bracket_text(text)

    return {"audio": audio_url, "image": image_url, "video": video_url}

def enrich_row_with_media_text(row: dict) -> Dict[str, Any]:
    """
    Se houver mídia:
      - ÁUDIO/VÍDEO: transcreve e substitui row['mensagem']['text'] pela transcrição.
      - IMAGEM: gera descrição curta e substitui row['mensagem']['text'] por "[Imagem] ...".
    Também marca 'media_processed' e anexa metadados úteis em row['mensagem']['meta']:
      - audio_url, audio_transcript
      - image_url, image_caption
      - video_url, video_transcript

    Retorna {"row": <row>, "changed": bool}.
    """
    msg = (row.get("mensagem") or {})
    meta = msg.get("meta") or {}

    # idempotência
    if meta.get("media_processed"):
        return {"row": row, "changed": False}

    media = _detect_media_urls_from_row(row)
    audio_url, image_url, video_url = media["audio"], media["image"], media["video"]

    new_text = None
    meta_changes: Dict[str, Any] = {}

    # ÁUDIO
    if audio_url and not new_text:
        data = _download(audio_url)
        if data:
            ext = mimetypes.guess_extension(mimetypes.guess_type(audio_url)[0] or "") or ".ogg"
            tr = _transcribe_bytes(data, filename=f"audio{ext}")
            if tr:
                new_text = tr
                meta_changes.update({"audio_url": audio_url, "audio_transcript": tr})

    # IMAGEM
    if image_url and not new_text:
        try:
            cap = _image_caption(image_url)
            if cap:
                new_text = f"[Imagem] {cap}"
                meta_changes.update({"image_url": image_url, "image_caption": cap})
            else:
                # análise falhou — usar fallback amigável e registrar meta indicando falha
                new_text = "Ocorreu um erro ao processar a imagem. Peça ao cliente para descrever o que deseja na imagem."
                meta_changes.update({"image_url": image_url, "image_caption_error": True})
        except Exception as _e_img:
            new_text = "Ocorreu um erro ao processar a imagem. Peça ao cliente para descrever o que deseja na imagem."
            try:
                meta_changes.update({"image_url": image_url, "image_caption_error": str(_e_img)})
            except Exception:
                meta_changes.update({"image_url": image_url, "image_caption_error": True})

    # VÍDEO
    if video_url and not new_text:
        data = _download(video_url)
        if data:
            ext = mimetypes.guess_extension(mimetypes.guess_type(video_url)[0] or "") or ".mp4"
            tr = _transcribe_bytes(data, filename=f"video{ext}")
            if tr:
                new_text = tr
                meta_changes.update({"video_url": video_url, "video_transcript": tr})

    if not new_text:
        return {"row": row, "changed": False}
    

    # aplica no row
    msg["text"] = new_text
    meta.update(meta_changes)
    meta["media_processed"] = True
    msg["meta"] = meta
    row["mensagem"] = msg

    return {"row": row, "changed": True}
# ==========================
# POLÍTICAS DA JULIA (gerente de projetos)
# ==========================
import re

STAFF_NAMES = {"thais", "marina", "mariane", "matheus", "vinicius", "katia"}

def _remove_staff_names(txt: str) -> str:
    t = txt or ""
    for n in STAFF_NAMES:
        t = re.sub(rf"\b{re.escape(n)}\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t)
    t = re.sub(r"[ ]+([,.!?])", r"\1", t)
    return t.strip()

def _should_ignore_reply(txt: str) -> bool:
    txt = (txt or "").lower().strip()
    FINALIZERS = {
        "ok","okk","okkk","okay","obrigado","obrigada","valeu","show",
        "perfeito","certo","combinado","fechou","tmj","👍","👌","🙏"
    }
    return txt in FINALIZERS

def _apply_manager_policies(msg_cliente: str, ai_texto: str) -> str:
    """Filtra e ajusta respostas conforme as diretrizes da gerente de projetos."""
    mc = (msg_cliente or "").strip().lower()
    draft = (ai_texto or "").strip()

    # Ignorar cortesia
    if _should_ignore_reply(mc):
        return ""

    # Limpeza geral (remove nomes da equipe que possam vazar)
    draft = _remove_staff_names(draft)

    # Se o modelo não gerou texto útil, podemos retornar uma das respostas
    # padronizadas, mas apenas em casos onde faz sentido confirmar/avisar.
    if not draft:
        # Se for relacionado a vídeo/mídia -> usar resposta de análise de vídeo
        if "vídeo" in mc or "video" in mc or "anexo" in mc:
            return "Vou analisar o vídeo e trago as observações necessárias em breve"

        # Palavras que indicam necessidade de checar com equipe/fornecedor
        needs_check_keywords = ["desconto", "fornecedor", "prazo", "disponibilidade", "confirmar", "verificar", "preço", "preco", "orçamento", "orcamento"]
        for k in needs_check_keywords:
            if k in mc:
                return "Vou verificar com a equipe e retorno com a atualização sobre os itens"

        # Caso contrário, devolve vazio para permitir que o fluxo decida (ou o modelo seja chamado)
        return ""

    return draft


# =================  FIM DO PRÉ-PROCESSAMENTO DE MÍDIA  =================
