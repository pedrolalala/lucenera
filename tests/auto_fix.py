import os
import re

def fix_missing_import():
    arquivo = 'routes/teams_suggest.py'
    with open(arquivo, 'r') as f:
        conteudo = f.read()
    imports_necessarios = [
        'import os',
        'import re',
        'import logging',
        'from flask import Blueprint, request, jsonify',
        'from services.supabase_client import supabase',
        'from services.zapi_service import enviar_mensagem_zapi'
    ]
    for imp in imports_necessarios:
        if imp not in conteudo:
            print(f"🔧 Adicionando import: {imp}")
            conteudo = imp + '\n' + conteudo
    with open(arquivo, 'w') as f:
        f.write(conteudo)
    print("✅ Imports corrigidos")

def fix_normalizar_telefone():
    arquivo = 'routes/teams_suggest.py'
    with open(arquivo, 'r') as f:
        conteudo = f.read()
    funcao_correta = '''
def normalizar_telefone(telefone):
    """Remove caracteres não-numéricos e garante formato E.164 brasileiro"""
    if not telefone:
        return None
    # Remove tudo que não é dígito
    apenas_digitos = re.sub('\\D', '', telefone)
    # Garante que começa com 55
    if not apenas_digitos.startswith('55'):
        apenas_digitos = '55' + apenas_digitos
    return apenas_digitos
'''
    pattern = r'def normalizar_telefone\(.*?\):(.*?)(?=\ndef |\nclass |\Z)'
    if re.search(pattern, conteudo, re.DOTALL):
        conteudo = re.sub(pattern, funcao_correta, conteudo, flags=re.DOTALL)
        with open(arquivo, 'w') as f:
            f.write(conteudo)
        print("✅ Função normalizar_telefone corrigida")
        return True
    else:
        print("⚠️  Função normalizar_telefone não encontrada")
        return False

def fix_validar_telefone():
    arquivo = 'routes/teams_suggest.py'
    with open(arquivo, 'r') as f:
        conteudo = f.read()
    funcao_correta = r'''
def validar_telefone(telefone):
    """Valida formato E.164 brasileiro: 5516999999999 (12 ou 13 dígitos)"""
    pattern = r'^55\d{10,11}$'
    return bool(re.match(pattern, telefone))
'''
    pattern = r'def validar_telefone\(.*?\):(.*?)(?=\ndef |\nclass |\Z)'
    if re.search(pattern, conteudo, re.DOTALL):
        conteudo = re.sub(pattern, funcao_correta, conteudo, flags=re.DOTALL)
        with open(arquivo, 'w') as f:
            f.write(conteudo)
        print("✅ Função validar_telefone corrigida")
        return True
    else:
        print("⚠️  Função validar_telefone não encontrada")
        return False

if __name__ == '__main__':
    print("🔧 Aplicando correções automáticas...\n")
    fix_missing_import()
    fix_normalizar_telefone()
    fix_validar_telefone()
    print("\n✅ Correções aplicadas. Re-execute os testes.")
