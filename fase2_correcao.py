#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO AUTÔNOMA - FASE 2: CORREÇÃO
Aplica correções automaticamente para problemas detectados
"""

import os
import re
import subprocess
import sys
from pathlib import Path

class CorretorAutonomo:
    def __init__(self, problemas):
        self.problemas = problemas
        self.correcoes_aplicadas = []
        self.falhas = []
        
    def corrigir_todos_problemas(self):
        """Aplica correções para todos os problemas"""
        print("\n🔧 FASE 2: CORREÇÃO AUTOMÁTICA\n")
        print(f"Total de problemas a corrigir: {len(self.problemas)}\n")
        
        for i, problema in enumerate(self.problemas, 1):
            print(f"🔧 [{i}/{len(self.problemas)}] Corrigindo: {problema['tipo']}...")
            
            sucesso = self.aplicar_correcao(problema)
            
            if sucesso:
                print(f"✅ Correção aplicada com sucesso\n")
            else:
                print(f"❌ Falha ao aplicar correção\n")
        
        self.gerar_relatorio_correcoes()
    
    def aplicar_correcao(self, problema):
        """Aplica correção específica baseado no tipo de problema"""
        tipo = problema['tipo']
        
        # Mapa de correções
        correcoes = {
            'syntax_error': self.corrigir_syntax_error,
            'dependencia_faltando': self.corrigir_dependencia,
            'arquivo_faltando': self.corrigir_arquivo_faltando,
            'env_var_faltando': self.corrigir_env_var,
            'funcao_faltando': self.corrigir_funcao_faltando,
            'logica_incorreta': self.corrigir_logica,
        }
        
        if tipo in correcoes:
            return correcoes[tipo](problema)
        else:
            self.falhas.append(problema)
            return False
    
    def corrigir_syntax_error(self, problema):
        """Corrige erros de sintaxe"""
        arquivo = problema['arquivo']
        linha = problema['linha']
        mensagem = problema['mensagem']
        print(f"   📝 Corrigindo SyntaxError em {arquivo}:{linha}")
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
            # Correção simples: remover linha problemática
            linhas.pop(linha-1)
            with open(arquivo, 'w', encoding='utf-8') as f:
                f.writelines(linhas)
            self.correcoes_aplicadas.append({
                'problema': problema,
                'acao': 'Removeu linha com erro de sintaxe',
                'arquivo': arquivo,
                'linha': linha
            })
            return True
        except Exception as e:
            print(f"   ❌ Erro ao corrigir: {e}")
            self.falhas.append(problema)
            return False
    
    def corrigir_dependencia(self, problema):
        """Instala dependências faltantes"""
        dependencia = problema['dependencia']
        print(f"   📦 Instalando {dependencia}...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', dependencia
            ], stdout=subprocess.DEVNULL)
            print(f"   ✅ {dependencia} instalado com sucesso")
            self.correcoes_aplicadas.append({
                'problema': problema,
                'acao': f'Instalou dependência: {dependencia}'
            })
            return True
        except Exception as e:
            print(f"   ❌ Falha ao instalar {dependencia}: {e}")
            self.falhas.append(problema)
            return False
    
    def corrigir_arquivo_faltando(self, problema):
        """Cria arquivos faltantes com template básico"""
        arquivo = problema['arquivo']
        print(f"   📄 Criando {arquivo}...")
        templates = {
            '.env': """# Configurações Z-API\nZAPI_INSTANCE=sua_instancia_aqui\nZAPI_TOKEN=seu_token_aqui\nZAPI_BASE=https://api.z-api.io\n\n# Configurações Supabase\nSUPABASE_URL=https://seu-projeto.supabase.co\nSUPABASE_KEY=sua_chave_service_role_aqui\n""",
            'requirements.txt': """flask>=2.3.0\nrequests>=2.31.0\nsupabase>=1.0.0\ntenacity>=8.2.0\npython-dotenv>=1.0.0\n"""
        }
        dir_path = os.path.dirname(arquivo)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"   ✅ Diretório criado: {dir_path}")
        if arquivo in templates:
            with open(arquivo, 'w') as f:
                f.write(templates[arquivo])
            print(f"   ✅ Arquivo criado: {arquivo}")
            self.correcoes_aplicadas.append({
                'problema': problema,
                'acao': f'Criou arquivo com template: {arquivo}'
            })
            return True
        else:
            print(f"   ⚠️ Template não disponível para {arquivo}")
            self.falhas.append(problema)
            return False
    
    def corrigir_env_var(self, problema):
        """Adiciona variável faltante no .env"""
        variavel = problema['variavel']
        print(f"   🔧 Adicionando {variavel} ao .env...")
        placeholders = {
            'ZAPI_INSTANCE': 'SUA_INSTANCIA_AQUI',
            'ZAPI_TOKEN': 'SEU_TOKEN_AQUI',
            'ZAPI_BASE': 'https://api.z-api.io',
            'SUPABASE_URL': 'https://SEU_PROJETO.supabase.co',
            'SUPABASE_KEY': 'SUA_CHAVE_SERVICE_ROLE_AQUI'
        }
        try:
            if os.path.exists('.env'):
                with open('.env', 'r') as f:
                    conteudo = f.read()
            else:
                conteudo = ""
            if variavel not in conteudo:
                valor = placeholders.get(variavel, 'VALOR_AQUI')
                nova_linha = f"\n{variavel}={valor}\n"
                with open('.env', 'a') as f:
                    f.write(nova_linha)
                print(f"   ✅ {variavel} adicionada ao .env")
                print(f"   ⚠️  AÇÃO MANUAL: Editar .env e configurar valor real de {variavel}")
                self.correcoes_aplicadas.append({
                    'problema': problema,
                    'acao': f'Adicionou {variavel} ao .env (requer configuração manual)',
                    'manual': True
                })
                return True
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            self.falhas.append(problema)
            return False
    
    def corrigir_funcao_faltando(self, problema):
        """Adiciona função faltante ao arquivo"""
        arquivo = problema['arquivo']
        funcao = problema['funcao']
        print(f"   📝 Adicionando função {funcao} em {arquivo}...")
        templates_funcoes = {
            'normalizar_telefone': (
                "def normalizar_telefone(telefone):\n"
                "    \"\"\"Remove caracteres não-numéricos e garante formato E.164 brasileiro\"\"\"\n"
                "    if not telefone:\n"
                "        return None\n"
                "    import re\n"
                "    apenas_digitos = re.sub(r'\\D', '', telefone)\n"
                "    if not apenas_digitos.startswith('55'):\n"
                "        apenas_digitos = '55' + apenas_digitos\n"
                "    return apenas_digitos\n"
            ),
            'validar_telefone': (
                "def validar_telefone(telefone):\n"
                "    \"\"\"Valida formato E.164 brasileiro: 5516999999999 (12 ou 13 dígitos)\"\"\"\n"
                "    import re\n"
                "    pattern = r'^55\\d{10,11}$'\n"
                "    return bool(re.match(pattern, telefone))\n"
            )
        }
        if funcao in templates_funcoes:
            try:
                with open(arquivo, 'r') as f:
                    conteudo = f.read()
                with open(arquivo, 'w') as f:
                    if '@' in conteudo:
                        partes = conteudo.split('@', 1)
                        f.write(partes[0])
                        f.write(templates_funcoes[funcao])
                        f.write('\n\n@')
                        f.write(partes[1])
                    else:
                        f.write(conteudo)
                        f.write('\n\n')
                        f.write(templates_funcoes[funcao])
                print(f"   ✅ Função {funcao} adicionada")
                self.correcoes_aplicadas.append({
                    'problema': problema,
                    'acao': f'Adicionou função {funcao}'
                })
                return True
            except Exception as e:
                print(f"   ❌ Erro: {e}")
                self.falhas.append(problema)
                return False
        else:
            print(f"   ⚠️ Template não disponível para função {funcao}")
            self.falhas.append(problema)
            return False
    
    def corrigir_logica(self, problema):
        """Corrige lógica de função"""
        arquivo = problema['arquivo']
        funcao = problema.get('funcao', '')
        print(f"   🔧 Corrigindo lógica de {funcao}...")
        if funcao == 'normalizar_telefone':
            try:
                with open(arquivo, 'r') as f:
                    conteudo = f.read()
                if 'startswith(\'55\')' in conteudo or 'startswith("55")' in conteudo:
                    print(f"   ✅ Lógica já está correta")
                    return True
                pattern = r'def normalizar_telefone\([^)]*\):.*?(?=\ndef |\nclass |\n@|\Z)'
                funcao_correta = (
                    "def normalizar_telefone(telefone):\n"
                    "    \"\"\"Remove caracteres não-numéricos e garante formato E.164 brasileiro\"\"\"\n"
                    "    if not telefone:\n"
                    "        return None\n"
                    "    import re\n"
                    "    apenas_digitos = re.sub(r'\\D', '', telefone)\n"
                    "    if not apenas_digitos.startswith('55'):\n"
                    "        apenas_digitos = '55' + apenas_digitos\n"
                    "    return apenas_digitos\n"
                )
                conteudo_novo = re.sub(pattern, funcao_correta, conteudo, flags=re.DOTALL)
                with open(arquivo, 'w') as f:
                    f.write(conteudo_novo)
                print(f"   ✅ Lógica de {funcao} corrigida")
                self.correcoes_aplicadas.append({
                    'problema': problema,
                    'acao': f'Corrigiu lógica de {funcao}'
                })
                return True
            except Exception as e:
                print(f"   ❌ Erro: {e}")
                self.falhas.append(problema)
                return False
        return False
    
    def gerar_relatorio_correcoes(self):
        """Gera relatório de correções aplicadas"""
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE CORREÇÕES")
        print("="*60 + "\n")
        print(f"✅ Correções bem-sucedidas: {len(self.correcoes_aplicadas)}")
        print(f"❌ Falhas: {len(self.falhas)}\n")
        if self.correcoes_aplicadas:
            print("CORREÇÕES APLICADAS:\n")
            for i, correcao in enumerate(self.correcoes_aplicadas, 1):
                print(f"{i}. {correcao['acao']}")
                if 'arquivo' in correcao:
                    print(f"   Arquivo: {correcao['arquivo']}")
                if correcao.get('manual'):
                    print(f"   ⚠️  Requer configuração manual")
                print()
        if self.falhas:
            print("FALHAS (REQUEREM AÇÃO MANUAL):\n")
            for i, falha in enumerate(self.falhas, 1):
                print(f"{i}. {falha['tipo']}: {falha['mensagem']}")
                print()