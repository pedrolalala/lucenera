# -*- coding: utf-8 -*-
import os
import re
import unicodedata
from copy import deepcopy
from typing import Any, Dict, Optional, Sequence

import requests

# ===== 1) DADOS DAS EQUIPES (fonte única) =====
EQUIPES = {
    "projetos": {
        "coordenacao": {
            "thais": {
                "nome": "Thais Gomes",
                "whatsapp": "5516997000842",
                "emails": ["thais@lucenera.com.br", "murillo@lucenera.com.br", "tricia@lucenera.com.br"],
            },
            "thairine": {
                "nome": "Thairine Silva",
                "whatsapp": "5516996464282",
                "emails": ["thairine@lucenera.com.br", "moara@lucenera.com.br", "adriana@lucenera.com.br", "giovana@lucenera.com.br"],
            },
            "marina": {
                "nome": "Marina Pousa",
                "whatsapp": "5516996454282",
                "emails": ["marina@lucenera.com.br", "giovanna.nori@lucenera.com.br", "isabella@lucenera.com.br", "ketlyn@lucenera.com.br"],
            },
            "mariane": {
                "nome": "Mariane Ribeiro",
                "whatsapp": "5516997000042",
                "emails": [],  # adicione se quiser derivar nomes a partir de email
            },
            "katia": {
                "nome": "Katia Alves",
                "whatsapp": "5516997702520",
                "emails": ["katia@lucenera.com.br"],
            },
        }
    },
    "financeiro": {
        "vinicius": {
            "nome": "Vinicius",
            "whatsapp": None,  # acionado via notificação interna
            "emails": [],
        }
    },
    "estoque": {
        "matheus": {
            "nome": "Matheus",
            "whatsapp": None,  # acionado via notificação interna
            "emails": [],
        }
    }
}

# ===== 2) HELPERS: extrair primeiros nomes de e-mails =====
_SPLIT_RE = re.compile(r"[.\-_+]+")

def primeiro_nome_de_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    local = email.split("@", 1)[0].strip()
    token = _SPLIT_RE.split(local)[0] or local
    token = re.sub(r"\d+", "", token).strip()
    return token.capitalize() if token else ""

def nomes_unicos(emails):
    seen, out = set(), []
    for e in emails or []:
        nome = primeiro_nome_de_email(e)
        if nome and nome not in seen:
            seen.add(nome)
            out.append(nome)
    return out

# ===== 3) AUGMENT: inclui `equipe_nomes` em cada nó que tiver emails/nome =====
def _augment_node(node: dict):
    emails = node.get("emails")
    if isinstance(emails, list):
        node["equipe_nomes"] = nomes_unicos(emails)
    elif "nome" in node and "equipe_nomes" not in node:
        primeiro = (node["nome"].split()[0].capitalize() if node.get("nome") else "")
        node["equipe_nomes"] = [primeiro] if primeiro else []
    for v in list(node.values()):
        if isinstance(v, dict):
            _augment_node(v)

def build_equipes_aug():
    data = deepcopy(EQUIPES)
    for v in data.values():
        if isinstance(v, dict):
            _augment_node(v)
    return data

EQUIPES_AUG = build_equipes_aug()

# ===== 4) UTIL: números internos (para bloqueio) =====
INTERNAL_NUMBERS = {
    "5516997000842",  # Thais
    "5516997000042",  # Mariane
    "5516996464282",  # Thairine
    "5516996454282",  # Marina
    "5516997702520",  # Katia
}

INTERNAL_WHATS = {
    # coordenações
    EQUIPES["projetos"]["coordenacao"]["thais"]["whatsapp"],
    EQUIPES["projetos"]["coordenacao"]["thairine"]["whatsapp"],
    EQUIPES["projetos"]["coordenacao"]["marina"]["whatsapp"],
    EQUIPES["projetos"]["coordenacao"]["mariane"]["whatsapp"],
    EQUIPES["projetos"]["coordenacao"]["katia"]["whatsapp"],
    # Número adicional marcado como interno (adicionado para bloquear IA mas manter histórico)
    "5516988579992",
}
INTERNAL_WHATS = {w for w in INTERNAL_WHATS if w}  # remove None
INTERNAL_WHATS |= INTERNAL_NUMBERS

_INTERNAL_DIGITS = {"".join(ch for ch in n if ch.isdigit()) for n in INTERNAL_WHATS}


def _digits_only(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_text(*parts: str) -> str:
    joined = " ".join(p for p in parts if p)
    if not joined:
        return ""
    text = unicodedata.normalize("NFKD", joined)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def _flatten_analysis(analysis: Any) -> str:
    if analysis is None:
        return ""
    if isinstance(analysis, str):
        return analysis
    if isinstance(analysis, dict):
        return " ".join(_flatten_analysis(v) for v in analysis.values())
    if isinstance(analysis, (list, tuple, set)):
        return " ".join(_flatten_analysis(v) for v in analysis)
    return str(analysis)


_FINANCE_TERMS = {
    "pagamento", "pagamentos", "pagto", "pagamento antecipado", "pagamento parcial",
    "forma de pagamento", "formas de pagamento", "condicao", "condicoes", "condicao de pagamento",
    "sinal", "entrada", "adiantamento", "reserva", "parcela", "parcelas", "parcelamento",
    "transferencia", "transferencias", "pix", "pix recebido", "pix confirmado", "pix pendente",
    "comprovante pix", "comprovante de pix", "chave pix", "copia e cola", "pix copia e cola",
    "boleto", "boletos", "comprovante", "deposito", "nota fiscal", "nota de servico", "nota de serviço",
    "nf", "nfe", "danfe", "faturamento", "pedido", "pedidos", "contrato", "contratos",
    "valor", "valores", "orcamento", "orcamentos", "proposta", "propostas", "aprovacao", "aprovacoes",
    "cobranca", "cobrancas", "recebimento", "recebimentos",
}

_FINANCE_SALES_TERMS = {
    "venda", "vendas", "venda fechada", "vendas fechadas", "fechar venda", "fechar a venda",
    "fechou a venda", "fechou venda", "fechou hoje", "cliente fechou", "cliente fechou hoje",
    "negocio fechado", "negocio fechado hoje", "fechou negocio", "fechar negocio",
    "proposta aprovada", "proposta aceita", "orcamento aprovado", "orcamento aceito",
    "pedido fechado", "pedido confirmado", "pedido aprovado", "pedido de compra",
    "contrato fechado", "fechar contrato", "contrato assinado",
}

_FINANCE_ALL_TERMS = _FINANCE_TERMS | _FINANCE_SALES_TERMS

_FINANCE_REGEX = [
    re.compile(r"\b(?:pagto|pagamento|parcela|parcelas|sinal|entrada|adiantamento|pix|boleto|transferencia|contrato|pedido|orcamento|proposta|comprovante)\b"),
    re.compile(r"nota\s+fiscal"),
    re.compile(r"nf\s*de\s*remessa"),
    re.compile(r"(?:fechou|fechar|fechada|fechado)\s+(?:a\s+)?(?:venda|negocio|contrato|proposta|pedido)"),
    re.compile(r"chave\s+pix"),
    re.compile(r"pix\s*(?:copia\s*e\s*cola|confirmado|recebido|agendado|pendente)?"),
]

_ESTOQUE_TERMS = {
    "estoque", "logistica", "logistico", "entrega", "entregas", "entregar", "entregue",
    "retirada", "retirar", "coleta", "coletar", "expedicao", "expedicoes", "remessa", "remessas",
    "roteiro", "separar", "separacao", "separacao de material", "enderecamento", "enderecamento",
}

_ESTOQUE_PHRASES = {
    "separar material", "separacao de material", "nf de remessa", "nota fiscal de remessa",
    "agendar entrega", "agendamento de entrega", "horario de entrega", "endereco de entrega",
    "retirada agendada", "coleta agendada", "coleta programada", "entrega programada",
}

def extrair_intencao_financeiro(
    texto: str,
    history_lines: Optional[Sequence[str]] = None,
    analysis_text: Optional[str] = None,
    **kwargs,
) -> bool:
    if history_lines is None:
        history_lines = kwargs.get("historico")
    if analysis_text is None:
        analysis_text = kwargs.get("analysis_text")

    history_joined = " ".join(history_lines or [])
    contexto = _normalize_text(texto, history_joined, analysis_text or "")
    if not contexto:
        return False
    if any(term in contexto for term in _FINANCE_ALL_TERMS):
        return True
    return any(regex.search(contexto) for regex in _FINANCE_REGEX)


def extrair_intencao_estoque(
    texto: str,
    history_lines: Optional[Sequence[str]] = None,
    analysis_text: Optional[str] = None,
    **kwargs,
) -> bool:
    if history_lines is None:
        history_lines = kwargs.get("historico")
    if analysis_text is None:
        analysis_text = kwargs.get("analysis_text")

    history_list = list(history_lines or [])
    history_text = " ".join(history_list)
    history_norm = _normalize_text(history_text)

    if history_norm:
        for token in ("entrega", "entregas", "retirada", "coleta", "separar", "material", "remessa", "estoque", "expedicao", "separacao"):
            if token in history_norm:
                return True

    contexto = _normalize_text(texto, history_text, analysis_text or "")
    if not contexto:
        return False
    for phrase in _ESTOQUE_PHRASES:
        if phrase in contexto:
            return True
    return any(term in contexto for term in _ESTOQUE_TERMS)


def is_internal_message(row_or_parsed: Dict[str, Any]) -> bool:
    """Retorna True se a mensagem deve ser tratada como comunicação interna."""
    if not isinstance(row_or_parsed, dict):
        return False

    # Não marcar status@broadcast como interno
    chat_phone = row_or_parsed.get("chat_phone") or row_or_parsed.get("telefone") or row_or_parsed.get("phone") or ""
    if chat_phone == "status@broadcast":
        return False

    tel = (
        row_or_parsed.get("telefone")
        or row_or_parsed.get("phone")
        or row_or_parsed.get("raw_telefone")
        or ""
    )
    if _digits_only(tel) in _INTERNAL_DIGITS:
        return True

    if row_or_parsed.get("from_me") is True or row_or_parsed.get("fromMe") is True:
        return True

    mensagem = row_or_parsed.get("mensagem") or {}
    if isinstance(mensagem, dict):
        meta = mensagem.get("meta") or {}
        if meta.get("from_me") is True or meta.get("fromMe") is True:
            return True

    direction = (row_or_parsed.get("direction") or "").strip().lower()
    if direction == "out":
        return True

    if _digits_only(chat_phone) in _INTERNAL_DIGITS:
        return True

    return False


def decidir_canal_teams_from_row(row: dict, history_lines: Optional[Sequence[str]] = None) -> str:
    """
    Decide para qual canal do Teams mandar a notificação,
    com base na análise/intenção da mensagem.
    Retorna: "projetos", "admin" ou "estoque".
    Heurística:
    - Se `row.get('analysis')` for dict, tenta inspecionar campos comuns como
      'area', 'category', 'intent' ou 'route'.
    - Senão, busca palavras-chave no texto da mensagem.
    """
    if not isinstance(row, dict):
        return "projetos"

    telefone = _digits_only(row.get("telefone")) if row.get("telefone") else ""
    if not telefone:
        try:
            telefone = _digits_only((row.get("mensagem") or {}).get("meta", {}).get("chat_phone"))
        except Exception:
            telefone = ""
    if telefone and telefone in ENTREGADORES_WHATS:
        print(f"[ROUTING] canal=entregas telefone={telefone}", flush=True)
        return "entregas"

    try:
        mensagem_texto = (row.get("mensagem") or {}).get("text") or ""
    except Exception:
        mensagem_texto = ""

    try:
        texto_ai = row.get("ai_draft") or ""
    except Exception:
        texto_ai = ""

    texto_candidato = mensagem_texto or texto_ai or ""
    texto_norm = _normalize_text(texto_candidato)

    # 1) tenta campos estruturados
    analysis = row.get("analysis")
    analysis_text = _flatten_analysis(analysis)
    historico = list(history_lines or [])

    def _log_routing(canal: str) -> None:
        try:
            analysis_snippet = (analysis_text or "")[:120]
            print(
                f"[ROUTING] canal={canal} texto_norm='{texto_norm[:120]}' analysis_text='{analysis_snippet}'",
                flush=True,
            )
        except Exception:
            pass

    if extrair_intencao_financeiro(
        mensagem_texto,
        history_lines=historico,
        analysis_text=analysis_text,
    ):
        _log_routing("admin")
        return "admin"

    if extrair_intencao_estoque(
        mensagem_texto,
        history_lines=historico,
        analysis_text=analysis_text,
    ):
        _log_routing("estoque")
        return "estoque"

    if isinstance(analysis, dict):
        for k in ("area", "category", "intent", "route", "label"):
            v = analysis.get(k)
            if isinstance(v, str) and v.strip():
                s = _normalize_text(v)
                if any(p in s for p in ("adm", "admin", "administracao", "administrativo", "financeiro", "boleto", "pagamento", "fatura", "pix", "chave pix")):
                    _log_routing("admin")
                    return "admin"
                if any(p in s for p in ("estoque", "logistica", "logistico", "almoxarifado", "expedicao", "entrega")):
                    _log_routing("estoque")
                    return "estoque"

    # 2) tenta texto bruto
    if any(p in texto_norm for p in (
        "adm", "admin", "administracao", "financeiro", "boleto", "pagamento", "fatura", "cobranca",
        "venda", "vendas", "proposta", "pedido", "orcamento", "contrato", "pix", "chave pix",
    )):
        _log_routing("admin")
        return "admin"
    if any(p in texto_norm for p in ("estoque", "logistica", "entrega", "coleta", "remessa", "nota fiscal", "nf", "rastrea")):
        _log_routing("estoque")
        return "estoque"

    # fallback
    _log_routing("projetos")
    return "projetos"


def get_teams_webhook_for_channel(channel: str) -> str | None:
    """
    Mapeia o canal lógico para a variável de ambiente do webhook.
    Retorna `None` se não houver webhook configurado para o canal.
    """
    ch = (channel or "").strip().lower()
    if ch == "admin" or ch == "financeiro":
        return os.getenv("TEAMS_WEBHOOK_ADMIN") or None
    if ch == "estoque" or ch == "log":
        return os.getenv("TEAMS_WEBHOOK_ESTQ") or None
    if ch == "entregas":
        return TEAMS_WEBHOOK_ENTREGAS or None
    # padrão projetos
    return os.getenv("TEAMS_WEBHOOK_URL") or None


TEAMS_WEBHOOK_ENTREGAS = (
    os.getenv("TEAMS_WEBHOOK_ENTREGAS")
    or os.getenv("TEAMS_WEBHOOK_ENTREGAFINALIZADA")
    or ""
)

if not TEAMS_WEBHOOK_ENTREGAS:
    print(
        ">> [TEAMS ENTREGAS] nenhum webhook configurado (TEAMS_WEBHOOK_ENTREGAS / TEAMS_WEBHOOK_ENTREGAFINALIZADA vazio).",
        flush=True,
    )

ENTREGADORES_WHATS = {
    _digits_only("xxxxxxxxxx"),  # entregador / numero de teste
}


def _notificar_entrega_no_teams(entrega: dict) -> None:
    if not TEAMS_WEBHOOK_ENTREGAS:
        print(
            ">> [TEAMS ENTREGAS] webhook não configurado, card não será enviado.",
            flush=True,
        )
        return

    entrega = entrega or {}
    status = (entrega.get("status") or "").strip().lower()
    codigo = (entrega.get("codigo_obra") or "-").strip() or "-"
    print(
        f">> [TEAMS ENTREGAS] enviando card para status='{status}' obra='{codigo}'",
        flush=True,
    )
    endereco = (entrega.get("endereco") or "-").strip()
    telefone = (entrega.get("telefone") or "-").strip() or "-"
    nome = (entrega.get("nome_entregador") or "-").strip() or "-"
    observacao = (entrega.get("observacao") or "-").strip() or "-"
    foto_url = (entrega.get("foto_url") or "").strip()

    if status != "concluida":
        resumo = f"Entrega em andamento - Obra {codigo}"
        titulo = "📦 Entrega iniciada"
        observacao = observacao if observacao else "—"
        foto_url = ""
    else:
        resumo = f"Entrega finalizada - Obra {codigo}"
        titulo = "📦 Entrega finalizada"
        if not observacao:
            observacao = "sem observações"

    card = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "0078D7",
        "summary": resumo,
        "title": titulo,
        "sections": [
            {
                "facts": [
                    {"name": "Obra", "value": codigo},
                    {"name": "Endereço", "value": endereco},
                    {"name": "Entregador", "value": f"{nome} ({telefone})"},
                    {"name": "Observações", "value": observacao},
                ],
                "markdown": True,
            }
        ],
    }

    if status == "concluida" and foto_url:
        card.setdefault("sections", []).append(
            {
                "text": "Foto da entrega",
                "images": [{"image": foto_url}],
            }
        )

    try:
        resp = requests.post(
            TEAMS_WEBHOOK_ENTREGAS,
            json=card,
            timeout=10,
        )
        if 200 <= resp.status_code < 300:
            print(
                ">> [TEAMS ENTREGAS] card enviado com sucesso.",
                flush=True,
            )
        else:
            print(
                f">> Teams entregas: resposta inesperada {resp.status_code} {resp.text[:200]}",
                flush=True,
            )
    except Exception as exc:  # pragma: no cover - apenas log
        print(f">> Teams entregas: erro ao enviar card: {exc}", flush=True)
