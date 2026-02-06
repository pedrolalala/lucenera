import sys
import os
from dotenv import load_dotenv

def test_dependencias():
    dependencias_obrigatorias = [
        'flask', 'requests', 'supabase', 'tenacity', 'dotenv'
    ]
    falhas = []
    for dep in dependencias_obrigatorias:
        try:
            __import__(dep)
            print(f"✅ {dep} instalado")
        except ImportError:
            print(f"❌ {dep} NÃO instalado")
            falhas.append(dep)
    if falhas:
        print(f"\n🔧 CORREÇÃO NECESSÁRIA: Instalar dependências faltantes")
        print(f"Execute: pip install {' '.join(falhas)}")
        return False
    print("\n✅ Todas as dependências estão instaladas\n")
    return True

def test_variaveis_ambiente():
    load_dotenv()
    variaveis_obrigatorias = {
        'ZAPI_ID_INSTANCE': 'ID da instância Z-API',
        'ZAPI_TOKEN': 'Token de autenticação Z-API',
        'ZAPI_BASE': 'URL base da Z-API',
        'SUPABASE_URL': 'URL do projeto Supabase',
        'SUPABASE_SERVICE_ROLE': 'Chave service_role do Supabase',
        'SUPABASE_SECRET_KEY': 'Chave secreta do Supabase'
    }
    falhas = []
    for var, descricao in variaveis_obrigatorias.items():
        valor = os.getenv(var)
        if not valor:
            print(f"❌ {var} NÃO configurada ({descricao})")
            falhas.append(var)
        else:
            print(f"✅ {var} configurada")
    if falhas:
        print(f"\n🔧 CORREÇÃO NECESSÁRIA: Configurar variáveis no arquivo .env")
        print(f"Faltam: {', '.join(falhas)}")
        return False
    print("\n✅ Todas as variáveis de ambiente estão configuradas\n")
    return True

if __name__ == '__main__':
    test_dependencias()
    test_variaveis_ambiente()
