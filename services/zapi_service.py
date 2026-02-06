
"""
Serviço de integração com Z-API para envio de mensagens WhatsApp
"""

import os
import requests
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

# CRÍTICO: Carregar .env ANTES de ler variáveis de ambiente
from dotenv import load_dotenv

from services.zapi_client import ZAPI_CLIENT_TOKEN
load_dotenv()

# Configurar logging
import logging
logger = logging.getLogger(__name__)


# Carregar variáveis de ambiente (agora o .env já foi carregado)
ZAPI_ID_INSTANCE = os.getenv('ZAPI_ID_INSTANCE')
ZAPI_TOKEN = os.getenv('ZAPI_TOKEN')
ZAPI_BASE = os.getenv('ZAPI_BASE', 'https://api.z-api.io')

# Validar configuração (agora as variáveis foram carregadas do .env)
if not ZAPI_ID_INSTANCE or not ZAPI_TOKEN:
    raise ValueError("ZAPI_ID_INSTANCE e ZAPI_TOKEN devem estar configurados no .env")

# Construir URL base
ZAPI_URL = f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type((requests.exceptions.RequestException, requests.exceptions.Timeout)),
    reraise=True
)
def enviar_mensagem_zapi_com_retry(telefone, mensagem):
    """
    Envia mensagem para WhatsApp via Z-API com retry automático
    
    Args:
        telefone (str): Número no formato E.164 (ex: 5516999999999)
        mensagem (str): Texto da mensagem (máx 4096 caracteres)
    
    Returns:
        dict: {"sucesso": True/False, "response": dados da API}
    
    Raises:
        requests.exceptions.RequestException: Se falhar após 3 tentativas
    """
    url = f"{ZAPI_BASE}/instances/{ZAPI_ID_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
    
    payload = {
        "phone": telefone,
        "message": mensagem
    }
    
    headers = {
        "Content-Type": "application/json",
        "Client-Token": ZAPI_CLIENT_TOKEN  
    }
    
    logger.info(f"[Z-API] Enviando mensagem para {telefone}")
    
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    
    if response.status_code == 200:
        logger.info(f"[Z-API SUCCESS] Telefone: {telefone}")
        return {"sucesso": True, "response": response.json()}
    else:
        logger.error(f"[Z-API ERROR] Status: {response.status_code}, Body: {response.text}")
        response.raise_for_status()


def enviar_mensagem_zapi(telefone, mensagem):
    """
    Wrapper que captura exceções e retorna dict ao invés de lançar erro
    
    Returns:
        dict: {"sucesso": True/False, "erro": mensagem de erro (se houver)}
    """
    try:
        resultado = enviar_mensagem_zapi_com_retry(telefone, mensagem)
        return resultado
    except Exception as e:
        logger.error(f"[Z-API FAILED após 3 tentativas] Telefone: {telefone}, Erro: {str(e)}")
        return {"sucesso": False, "erro": str(e)}
