
import sys
import os
# Adicionar diretório raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Carregar .env do diretório raiz
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Agora pode importar módulos do projeto
from routes.teams_suggest import normalizar_telefone, validar_telefone

def test_normalizacao_telefone():
    casos_teste = [
        ("5516999999999", "5516999999999"),
        ("16999999999", "5516999999999"),
        ("(16) 99999-9999", "5516999999999"),
        ("55 16 9 9999-9999", "5516999999999"),
        ("+55 16 99999-9999", "5516999999999"),
    ]
    falhas = []
    for input_tel, esperado in casos_teste:
        resultado = normalizar_telefone(input_tel)
        if resultado == esperado:
            print(f"✅ normalizar_telefone('{input_tel}') → '{resultado}'")
        else:
            print(f"❌ normalizar_telefone('{input_tel}') → '{resultado}' (esperado: '{esperado}')")
            falhas.append((input_tel, resultado, esperado))
    if falhas:
        print(f"\n🔧 CORREÇÃO NECESSÁRIA na função normalizar_telefone()")
        print(f"Falhas: {falhas}")
        return False
    print("\n✅ Normalização de telefone funcionando corretamente\n")
    return True

def test_validacao_telefone():
    casos_validos = ["5516999999999", "551633334444"]
    casos_invalidos = ["16999999999", "5516999", "abc", ""]
    falhas = []
    for telefone in casos_validos:
        if validar_telefone(telefone):
            print(f"✅ validar_telefone('{telefone}') → True")
        else:
            print(f"❌ validar_telefone('{telefone}') → False (deveria ser True)")
            falhas.append(telefone)
    for telefone in casos_invalidos:
        if not validar_telefone(telefone):
            print(f"✅ validar_telefone('{telefone}') → False")
        else:
            print(f"❌ validar_telefone('{telefone}') → True (deveria ser False)")
            falhas.append(telefone)
    if falhas:
        print(f"\n🔧 CORREÇÃO NECESSÁRIA na função validar_telefone()")
        return False
    print("\n✅ Validação de telefone funcionando corretamente\n")
    return True

if __name__ == '__main__':
    """
    Testes unitários para funções auxiliares
    """

    import sys
    sys.path.insert(0, '.')

    # CRÍTICO: Carregar .env ANTES de importar módulos do projeto (robusto para qualquer SO e diretório)
    from dotenv import load_dotenv
    import os
    import pathlib
    env_loaded = False
    env_path_abs = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_path_abs):
        load_dotenv(dotenv_path=env_path_abs)
        env_loaded = True
    elif os.path.exists('.env'):
        load_dotenv(dotenv_path='.env')
        env_loaded = True
    if not env_loaded:
        print('⚠️  .env não encontrado! Variáveis de ambiente podem não estar disponíveis.')

    # Agora pode importar módulos que dependem de variáveis de ambiente
    from routes.teams_suggest import normalizar_telefone, validar_telefone

    def test_normalizacao_telefone():
        """Testa normalização de telefone"""
        casos_teste = [
            # (input, esperado)
            ("5516999999999", "5516999999999"),  # Já normalizado
            ("16999999999", "5516999999999"),    # Sem código país
            ("(16) 99999-9999", "5516999999999"), # Com formatação
            ("55 16 9 9999-9999", "5516999999999"), # Com espaços
            ("+55 16 99999-9999", "5516999999999"), # Com +
        ]
    
        falhas = []
        for input_tel, esperado in casos_teste:
            resultado = normalizar_telefone(input_tel)
            if resultado == esperado:
                print(f"✅ normalizar_telefone('{input_tel}') → '{resultado}'")
            else:
                print(f"❌ normalizar_telefone('{input_tel}') → '{resultado}' (esperado: '{esperado}')")
                falhas.append((input_tel, resultado, esperado))
    
        if falhas:
            print(f"\n🔧 CORREÇÃO NECESSÁRIA na função normalizar_telefone()")
            print(f"Falhas: {falhas}")
            return False
    
        print("\n✅ Normalização de telefone funcionando corretamente\n")
        return True


    def test_validacao_telefone():
        """Testa validação de formato E.164"""
        casos_validos = [
            "5516999999999",   # Celular 9 dígitos
            "551633334444",    # Fixo 8 dígitos
        ]
    
        casos_invalidos = [
            "16999999999",     # Sem código país
            "5516999",         # Incompleto
            "abc",             # Não numérico
            "",                # Vazio
        ]
    
        falhas = []
    
        # Testar casos válidos
        for telefone in casos_validos:
            if validar_telefone(telefone):
                print(f"✅ validar_telefone('{telefone}') → True")
            else:
                print(f"❌ validar_telefone('{telefone}') → False (deveria ser True)")
                falhas.append(telefone)
    
        # Testar casos inválidos
        for telefone in casos_invalidos:
            if not validar_telefone(telefone):
                print(f"✅ validar_telefone('{telefone}') → False")
            else:
                print(f"❌ validar_telefone('{telefone}') → True (deveria ser False)")
                falhas.append(telefone)
    
        if falhas:
            print(f"\n🔧 CORREÇÃO NECESSÁRIA na função validar_telefone()")
            return False
    
        print("\n✅ Validação de telefone funcionando corretamente\n")
        return True


    if __name__ == '__main__':
        test_normalizacao_telefone()
        test_validacao_telefone()
