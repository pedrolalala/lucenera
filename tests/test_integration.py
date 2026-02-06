
import sys
import os

# Adicionar diretório raiz ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Carregar .env
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Importar módulos do projeto
from services.zapi_service import enviar_mensagem_zapi
from services.supabase_client import require_supabase_client

# Inicializar Supabase client
try:
    supabase_client = require_supabase_client()
    print("✅ Supabase client inicializado com sucesso")
except Exception as e:
    print(f"❌ Erro ao inicializar Supabase: {e}")
    supabase_client = None

import time

def test_envio_zapi():
    """Testa envio de mensagem via Z-API"""
    telefone_teste = "5516999999999"  # ← SEU NÚMERO AQUI
    mensagem_teste = "🧪 Teste de integração - Sistema Lucenera"
    print(f"🔄 Enviando mensagem de teste para {telefone_teste}...")
    try:
        resultado = enviar_mensagem_zapi(telefone_teste, mensagem_teste)
        if resultado:
            print("✅ Envio Z-API bem-sucedido")
            print(f"Resposta: {resultado}")
            return True
        else:
            print("❌ Falha no envio Z-API")
            return False
    except Exception as e:
        print(f"❌ Falha no envio Z-API")
        print(f"Erro: {e}")
        return False

def test_salvamento_supabase():
    """Testa salvamento no Supabase"""
    if not supabase_client:
        print("❌ Supabase client não disponível")
        return False
    print("🔄 Salvando registro de teste no Supabase...")
    registro_teste = {
        "telefone": "5516999999999",
        "mensagem": {"text": "Teste de integração", "raw": {}},
        "nome": {"display": "Teste Sistema"},
        "data": "2026-02-04T10:00:00Z",
        "status": "received",
        "fromMe": False,
        "origem": "teste_integracao",
        "used_ai": False,
        "approval_mode": True
    }
    try:
        # Inserir registro
        response = supabase_client.table("mensagens").insert(registro_teste).execute()
        if response.data and isinstance(response.data, list) and len(response.data) > 0:
            first_row = response.data[0]
            if isinstance(first_row, dict) and 'id_num' in first_row:
                print("✅ Salvamento no Supabase bem-sucedido")
                registro_id = first_row['id_num']  # PRIMARY KEY é id_num
                print(f"ID criado: {registro_id}")
                # Deletar registro de teste
                if registro_id:
                    supabase_client.table("mensagens").delete().eq('id_num', registro_id).execute()
                    print("🧹 Registro de teste removido")
                return True
            else:
                print(f"❌ Formato inesperado no retorno do Supabase: {first_row}")
                return False
        else:
            print("❌ Falha ao salvar no Supabase: Sem dados retornados")
            return False
    except Exception as e:
        print(f"❌ Falha ao salvar no Supabase: {e}")
        return False

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🧪 TESTE DE INTEGRAÇÃO - Z-API + SUPABASE")
    print("="*60 + "\n")
    # Teste 1: Z-API
    zapi_ok = test_envio_zapi()
    print()
    # Teste 2: Supabase
    supabase_ok = test_salvamento_supabase()
    print()
    # Resumo
    print("="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    print(f"Z-API: {'✅ OK' if zapi_ok else '❌ FALHOU'}")
    print(f"Supabase: {'✅ OK' if supabase_ok else '❌ FALHOU'}")
    print()
    if zapi_ok and supabase_ok:
        print("🎉 TODOS OS TESTES DE INTEGRAÇÃO PASSARAM!")
    else:
        print("⚠️  Alguns testes falharam. Verifique as configurações.")
