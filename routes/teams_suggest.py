import os
import re
import logging
from flask import Blueprint, request, jsonify, render_template, redirect
from services.supabase_client import require_supabase_client
from services.zapi_service import enviar_mensagem_zapi

# Definir blueprint antes de qualquer uso
teams_suggest_bp = Blueprint('teams_suggest', __name__)

# Configurar logger
logger = logging.getLogger(__name__)

# Funções auxiliares
def normalizar_telefone(telefone):
    """Remove caracteres não-numéricos e garante formato E.164 brasileiro"""
    if not telefone:
        return None
    # Exemplo: normalizar para 5516999999999
    telefone = re.sub(r'\D', '', telefone)
    if telefone.startswith('0'):
        telefone = telefone[1:]
    if telefone.startswith('55'):
        return telefone
    if telefone.startswith('1'):
        return '55' + telefone
    if len(telefone) == 11:
        return '55' + telefone
    return telefone

def validar_telefone(telefone):
    """Valida formato E.164 brasileiro: 5516999999999"""
    return isinstance(telefone, str) and telefone.startswith('55') and len(telefone) == 13

# === ROTA GET /suggest (formulário) ===
@teams_suggest_bp.route('/suggest', methods=['GET'])
def suggest_form():
    msg_id = request.args.get('id') or ''
    token = request.args.get('token') or ''
    mensagem_cliente = request.args.get('mensagem_cliente')
    resposta_bot = request.args.get('resposta_bot')
    telefone = request.args.get('telefone')
    categoria = request.args.get('categoria')

    # Buscar do banco se não vierem na query
    if msg_id and (mensagem_cliente is None or resposta_bot is None or telefone is None or categoria is None):
        try:
            supabase = require_supabase_client()
            res = supabase.table('mensagens').select('*').eq('id_num', int(msg_id)).execute()
            if res.data and len(res.data) > 0:
                row = res.data[0]
                # mensagem_cliente pode estar em row['mensagem'] (json)
                if mensagem_cliente is None:
                    msg = row.get('mensagem')
                    if isinstance(msg, dict):
                        mensagem_cliente = msg.get('text') or ''
                    elif isinstance(msg, str):
                        mensagem_cliente = msg
                    else:
                        mensagem_cliente = ''
                if resposta_bot is None:
                    resposta_bot = row.get('ai_draft') or row.get('final_out') or ''
                if telefone is None:
                    telefone = row.get('telefone') or ''
                if categoria is None:
                    categoria = row.get('categoria') or ''
        except Exception as e:
            logger.warning(f"[SUGGEST_FORM] Falha ao buscar dados do banco: {e}")
            if mensagem_cliente is None:
                mensagem_cliente = ''
            if resposta_bot is None:
                resposta_bot = ''
            if telefone is None:
                telefone = ''
            if categoria is None:
                categoria = ''
    # Garante que são strings simples
    mensagem_cliente = str(mensagem_cliente or '')
    resposta_bot = str(resposta_bot or '')
    telefone = str(telefone or '')
    categoria = str(categoria or '')
    return render_template('teams_suggest.html',
                          msg_id=msg_id,
                          token=token,
                          mensagem_cliente=mensagem_cliente,
                          resposta_bot=resposta_bot,
                          telefone=telefone,
                          categoria=categoria)

# === ROTA POST /suggest ===
@teams_suggest_bp.route('/suggest', methods=['POST'])
def suggest():
    import time, json, traceback
    inicio = time.time()
    try:
        data = request.get_json(silent=True) or {}
        telefone = data.get('telefone') or ''
        mensagem_sugerida = data.get('mensagem')
        msg_id = data.get('msg_id')
        contexto = data.get('contexto', {})
        resposta_bot = data.get('resposta_bot')

        # Buscar do banco se campos estiverem ausentes ou vazios
        if msg_id and (not contexto.get('mensagem_cliente') or not resposta_bot or not telefone):
            try:
                supabase = require_supabase_client()
                res = supabase.table('mensagens').select('*').eq('id_num', int(msg_id)).execute()
                if res.data and len(res.data) > 0:
                    row = res.data[0]
                    # mensagem_cliente pode estar em row['mensagem'] (json)
                    if not contexto.get('mensagem_cliente'):
                        msg = row.get('mensagem')
                        if isinstance(msg, dict):
                            contexto['mensagem_cliente'] = msg.get('text') or ''
                        elif isinstance(msg, str):
                            contexto['mensagem_cliente'] = msg
                        else:
                            contexto['mensagem_cliente'] = ''
                    if not resposta_bot:
                        resposta_bot = row.get('ai_draft') or row.get('final_out') or ''
                    if not telefone:
                        telefone = row.get('telefone') or ''
            except Exception as e:
                logger.warning(f"[SUGGEST] Falha ao buscar dados do banco: {e}")
                if not contexto.get('mensagem_cliente'):
                    contexto['mensagem_cliente'] = ''
                if not resposta_bot:
                    resposta_bot = ''
                if not telefone:
                    telefone = ''

        # Garante que são strings simples
        mensagem_cliente = str(contexto.get('mensagem_cliente') or '')
        resposta_bot = str(resposta_bot or '')
        telefone = str(telefone or '')

        # Token extraction from multiple sources
        token_json = data.get('token')
        token_form = request.form.get('token')
        token_args = request.args.get('token')
        token = token_json or token_form or token_args
        logger.info(f"[DEBUG] Token extraído do JSON: {token_json!r}")
        logger.info(f"[DEBUG] Token extraído do form: {token_form!r}")
        logger.info(f"[DEBUG] Token extraído da query string: {token_args!r}")
        logger.info(f"[DEBUG] Token final usado: {token!r}")

        # === 1. Validação de token e campos obrigatórios ===
        TEAMS_ACTION_TOKEN = os.getenv('TEAMS_ACTION_TOKEN')
        logger.info(f"[DEBUG] Token do .env: {TEAMS_ACTION_TOKEN!r}")
        logger.info(f"[DEBUG] Tokens são iguais? {token == TEAMS_ACTION_TOKEN}")
        if token != TEAMS_ACTION_TOKEN:
            logger.warning(f"[SUGGEST ERRO] Token inválido: recebido={token!r}")
            return jsonify({"success": False, "error": "Token inválido"}), 403
        if not mensagem_sugerida:
            logger.warning("[SUGGEST] Mensagem ausente")
            return jsonify({"success": False, "error": "Mensagem é obrigatória"}), 400
        if not msg_id:
            logger.warning("[SUGGEST] msg_id ausente")
            return jsonify({"success": False, "error": "msg_id é obrigatório"}), 400

        # Se telefone vier vazio, pular validação
        if telefone:
            telefone_normalizado = normalizar_telefone(telefone)
            if not validar_telefone(telefone_normalizado):
                logger.warning(f"[SUGGEST] Telefone inválido: {telefone}")
                return jsonify({
                    "success": False,
                    "error": "Telefone inválido. Use formato: 5516999999999"
                }), 400
        else:
            # Telefone vazio/ausente - permitir mas logar
            telefone_normalizado = None
            logger.info("[SUGGEST] Telefone não informado (permitido)")

        logger.info(f"[SUGGEST VALIDAÇÃO OK] Telefone: {telefone_normalizado}, msg_id: {msg_id}")

        # === 2. Enviar WhatsApp via Z-API (com retry) ===
        # Buscar dados extras se faltando
        if not contexto or not contexto.get('mensagem_cliente') or not contexto.get('categoria') or not contexto.get('intencao'):
            try:
                supabase = require_supabase_client()
                if msg_id:
                    res = supabase.table('mensagens').select('*').eq('id_num', msg_id).execute()
                    if res.data and len(res.data) > 0:
                        row = res.data[0]
                        if isinstance(row, dict):
                            if not contexto.get('mensagem_cliente'):
                                contexto['mensagem_cliente'] = row.get('mensagem', '')
                            if not contexto.get('categoria'):
                                contexto['categoria'] = row.get('categoria', '')
                            if not contexto.get('intencao'):
                                contexto['intencao'] = row.get('intencao', '')
                            if not telefone:
                                telefone = row.get('telefone', '')
                            if not resposta_bot:
                                resposta_bot = row.get('resposta_bot', '')
            except Exception as e:
                logger.warning(f"[SUGGEST] Falha ao buscar dados extras: {e}")

        categoria = contexto.get('categoria')
        intencao = contexto.get('intencao')
        registro = {
            'telefone': telefone_normalizado,
            'mensagem_cliente': mensagem_cliente,
            'resposta_humana_correta': mensagem_sugerida,
            'resposta_bot_original': resposta_bot,
            'categoria': categoria,
            'intencao': intencao,
            'contexto': json.dumps(contexto) if contexto else None,
            'origem': 'teams_suggest'
        }

        # Salvar feedback no Supabase
        registrada_supabase = False
        erro_supabase = None
        try:
            supabase = require_supabase_client()
            logger.info(f"[SUGGEST SUPABASE] Inserindo registro: {msg_id}")
            supabase.table('feedback_respostas').insert(registro).execute()
            registrada_supabase = True
            logger.info(f"[SUGGEST SUPABASE SUCESSO] Feedback registrado com sucesso")
        except Exception as e:
            erro_supabase = str(e)
            logger.error(f"[SUGGEST SUPABASE ERRO] Falha ao salvar: {erro_supabase}")
            logger.error(f"[SUGGEST SUPABASE TRACEBACK] {traceback.format_exc()}")
            registrada_supabase = False

        # Enviar WhatsApp via ZAPI após salvar
        enviada_whatsapp = False
        zapi_result = None
        if mensagem_sugerida and telefone_normalizado and not mensagem_sugerida.strip().startswith('[TESTE'):
            for tentativa in range(1, 4):
                try:
                    logger.info(f"[SUGGEST ZAPI] Tentativa {tentativa}/3 para {telefone_normalizado}")
                    zapi_result = enviar_mensagem_zapi(telefone_normalizado, mensagem_sugerida)
                    if zapi_result and zapi_result.get('sucesso'):
                        enviada_whatsapp = True
                        logger.info(f"[SUGGEST ZAPI SUCESSO] Mensagem enviada")
                        break
                    else:
                        logger.warning(f"[SUGGEST ZAPI FALHA] Tentativa {tentativa} falhou: {zapi_result}")
                        if tentativa < 3:
                            time.sleep(2)
                except Exception as e:
                    logger.warning(f"[SUGGEST ZAPI ERRO] Tentativa {tentativa}: {str(e)}")
                    if tentativa < 3:
                        time.sleep(2)

        # === 3. SEMPRE salvar feedback no Supabase ===
        registrada_supabase = False
        erro_supabase = None
        try:
            supabase = require_supabase_client()
            mensagem_cliente = contexto.get('mensagem_cliente') or 'Não informado'
            categoria = contexto.get('categoria')
            intencao = contexto.get('intencao')
            registro = {
                'telefone': telefone_normalizado,
                'mensagem_cliente': mensagem_cliente,
                'resposta_humana_correta': mensagem_sugerida,
                'resposta_bot_original': resposta_bot,
                'categoria': categoria,
                'intencao': intencao,
                'contexto': json.dumps(contexto) if contexto else None,
                'origem': 'teams_suggest'
            }
            logger.info(f"[SUGGEST SUPABASE] Inserindo registro: {msg_id}")
            supabase.table('feedback_respostas').insert(registro).execute()
            registrada_supabase = True
            logger.info(f"[SUGGEST SUPABASE SUCESSO] Feedback registrado com sucesso")
        except Exception as e:
            erro_supabase = str(e)
            logger.error(f"[SUGGEST SUPABASE ERRO] Falha ao salvar: {erro_supabase}")
            logger.error(f"[SUGGEST SUPABASE TRACEBACK] {traceback.format_exc()}")
            registrada_supabase = False

        # === 4. Resposta detalhada ===
        tempo_ms = int((time.time() - inicio) * 1000)
        logger.info(f"[SUGGEST COMPLETO] WhatsApp: {enviada_whatsapp}, Supabase: {registrada_supabase}, Tempo: {tempo_ms}ms")
        return jsonify({
            "success": True,
            "enviada_whatsapp": enviada_whatsapp,
            "registrada_supabase": registrada_supabase,
            "telefone": telefone_normalizado,
            "msg_id": msg_id,
            "tempo_processamento_ms": tempo_ms,
            "zapi_result": zapi_result,
            "erro_supabase": erro_supabase
        }), 200
    except Exception as e:
        logger.error(f"[SUGGEST ERRO FATAL] {str(e)}")
        logger.error(f"[SUGGEST TRACEBACK] {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
            "enviada_whatsapp": False,
            "registrada_supabase": False
        }), 200

# === ROTA GET /approve ===
@teams_suggest_bp.route('/approve', methods=['GET'])
def approve():
    import time
    inicio = time.time()
    token = request.args.get('token')
    TEAMS_ACTION_TOKEN = os.getenv('TEAMS_ACTION_TOKEN')
    logger.info(f"[APPROVE] Token recebido: {token!r}")
    logger.info(f"[APPROVE] Token esperado: {TEAMS_ACTION_TOKEN!r}")
    if token != TEAMS_ACTION_TOKEN:
        logger.warning("[APPROVE] Token inválido")
        return "forbidden", 403
    rid = request.args.get('id')
    if not rid:
        logger.warning("[APPROVE] ID obrigatório ausente")
        return "id obrigatório", 400
    try:
        supabase = require_supabase_client()
        try:
            rid_int = int(rid)
        except Exception:
            logger.warning(f"[APPROVE] ID inválido: {rid}")
            return f"erro: id inválido", 400
        res = supabase.table('mensagens').select('*').eq('id_num', rid_int).execute()
        if not res.data or len(res.data) == 0:
            logger.warning(f"[APPROVE] Nenhum registro encontrado para id_num={rid}")
            return f"erro: registro não encontrado", 404
        row = res.data[0]
        if isinstance(row, dict):
            telefone = row.get('telefone')
            resposta = row.get('ai_draft') or row.get('final_out')
        else:
            telefone = None
            resposta = None
        if not telefone or not resposta:
            logger.warning(f"[APPROVE] Telefone ou resposta ausente para id_num={rid}")
            return f"erro: telefone ou resposta ausente", 400
        # Enviar para ZAPI
        zapi_result = enviar_mensagem_zapi(telefone, resposta)
        logger.info(f"[APPROVE] Mensagem enviada via ZAPI para {telefone}: {zapi_result}")
        tempo_ms = int((time.time() - inicio) * 1000)
        logger.info(f"[APPROVE COMPLETO] Tempo: {tempo_ms}ms")
        return f"Mensagem aprovada e enviada para {telefone}", 200
    except Exception as e:
        logger.error(f"[APPROVE ERRO] {str(e)}")
        return f"erro: {str(e)}", 500

# === ROTA GET /reject ===
@teams_suggest_bp.route('/reject', methods=['GET'])
def reject():
    token = request.args.get('token')
    TEAMS_ACTION_TOKEN = os.getenv('TEAMS_ACTION_TOKEN')
    if token != TEAMS_ACTION_TOKEN:
        return "forbidden", 403
    rid = request.args.get('id')
    if not rid:
        return "id obrigatório", 400
    try:
        supabase = require_supabase_client()
        supabase.table('feedback_respostas')\
            .update({'status': 'rejeitada', 'rejeitada_em': 'now()'})\
            .eq('id', rid)\
            .execute()
        return redirect('/admin')
    except Exception as e:
        return f"erro: {str(e)}", 500


