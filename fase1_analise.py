#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO AUTÔNOMA - FASE 1: ANÁLISE
Execute este script para análise completa do projeto
"""

import os
import ast
import re
import subprocess
import sys
from pathlib import Path

class AnalisadorAutonomo:
    def __init__(self):
        self.problemas = []
        self.correcoes_aplicadas = []
        
    def analisar_projeto_completo(self):
        """Analisa todos os arquivos Python do projeto"""
        print("🔍 FASE 1: ANÁLISE COMPLETA DO PROJETO\n")
        
        # 1. Verificar estrutura de arquivos
        self.verificar_estrutura()
        
        # 2. Analisar sintaxe de todos os arquivos Python
        self.analisar_sintaxe_todos_arquivos()
        
        # 3. Verificar imports e dependências
        self.verificar_dependencias()
        
        # 4. Validar configuração (.env)
        self.validar_configuracao()
        
        # 5. Analisar lógica de funções críticas
        self.analisar_logica()
        
        return len(self.problemas) == 0
    
    def verificar_estrutura(self):
        """Verifica se todos os arquivos necessários existem"""
        arquivos_necessarios = [
            'app.py',
            'routes/teams_suggest.py',
            'services/zapi_service.py',
            'services/supabase_client.py',
            '.env',
            'requirements.txt'
        ]
        
        for arquivo in arquivos_necessarios:
            if not os.path.exists(arquivo):
                self.problemas.append({
                    'tipo': 'arquivo_faltando',
                    'arquivo': arquivo,
                    'severidade': 'CRÍTICO',
                    'mensagem': f'Arquivo obrigatório não encontrado: {arquivo}'
                })
                print(f"❌ CRÍTICO: {arquivo} não encontrado")
            else:
                print(f"✅ {arquivo} encontrado")
    
    def analisar_sintaxe_todos_arquivos(self):
        """Verifica sintaxe de todos os arquivos .py"""
        print("\n🔍 Analisando sintaxe de arquivos Python...\n")
        
        for arquivo_py in Path('.').rglob('*.py'):
            if '.venv' in str(arquivo_py) or 'venv' in str(arquivo_py):
                continue
                
            try:
                with open(arquivo_py, 'r', encoding='utf-8') as f:
                    codigo = f.read()
                
                # Tentar compilar o código
                ast.parse(codigo)
                print(f"✅ {arquivo_py}: Sintaxe válida")
                
            except SyntaxError as e:
                self.problemas.append({
                    'tipo': 'syntax_error',
                    'arquivo': str(arquivo_py),
                    'linha': e.lineno,
                    'mensagem': str(e.msg),
                    'severidade': 'CRÍTICO',
                    'texto_linha': e.text,
                    'offset': e.offset
                })
                print(f"❌ {arquivo_py}:{e.lineno} - SyntaxError: {e.msg}")
                
            except Exception as e:
                self.problemas.append({
                    'tipo': 'erro_leitura',
                    'arquivo': str(arquivo_py),
                    'mensagem': str(e),
                    'severidade': 'ALTO'
                })
                print(f"⚠️ {arquivo_py} - Erro ao ler: {e}")
    
    def verificar_dependencias(self):
        """Verifica se todas as dependências estão instaladas"""
        print("\n🔍 Verificando dependências...\n")
        
        dependencias_necessarias = [
            'flask',
            'requests', 
            'supabase',
            'tenacity',
            'python-dotenv'
        ]
        
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'freeze'],
                capture_output=True,
                text=True
            )
            instaladas = result.stdout.lower()
            
            for dep in dependencias_necessarias:
                if dep.lower() in instaladas:
                    print(f"✅ {dep} instalado")
                else:
                    self.problemas.append({
                        'tipo': 'dependencia_faltando',
                        'dependencia': dep,
                        'severidade': 'ALTO',
                        'mensagem': f'Dependência não instalada: {dep}'
                    })
                    print(f"❌ {dep} NÃO instalado")
                    
        except Exception as e:
            print(f"⚠️ Não foi possível verificar dependências: {e}")
    
    def validar_configuracao(self):
        """Valida arquivo .env"""
        print("\n🔍 Validando configuração (.env)...\n")
        
        if not os.path.exists('.env'):
            self.problemas.append({
                'tipo': 'config_faltando',
                'arquivo': '.env',
                'severidade': 'CRÍTICO',
                'mensagem': 'Arquivo .env não encontrado'
            })
            print("❌ CRÍTICO: Arquivo .env não encontrado")
            return
        
        from dotenv import load_dotenv
        load_dotenv()
        
        variaveis_obrigatorias = [
            'ZAPI_INSTANCE',
            'ZAPI_TOKEN',
            'ZAPI_BASE',
            'SUPABASE_URL',
            'SUPABASE_KEY'
        ]
        
        for var in variaveis_obrigatorias:
            valor = os.getenv(var)
            if not valor:
                self.problemas.append({
                    'tipo': 'env_var_faltando',
                    'variavel': var,
                    'severidade': 'CRÍTICO',
                    'mensagem': f'Variável de ambiente não configurada: {var}'
                })
                print(f"❌ {var} não configurada")
            else:
                print(f"✅ {var} configurada")
    
    def analisar_logica(self):
        """Analisa lógica de funções críticas"""
        print("\n🔍 Analisando lógica de funções...\n")
        
        # Verificar função normalizar_telefone
        if os.path.exists('routes/teams_suggest.py'):
            with open('routes/teams_suggest.py', 'r') as f:
                conteudo = f.read()
                
            # Verificar se função normalizar_telefone existe
            if 'def normalizar_telefone' not in conteudo:
                self.problemas.append({
                    'tipo': 'funcao_faltando',
                    'arquivo': 'routes/teams_suggest.py',
                    'funcao': 'normalizar_telefone',
                    'severidade': 'ALTO',
                    'mensagem': 'Função normalizar_telefone não encontrada'
                })
                print("❌ Função normalizar_telefone não encontrada")
            else:
                print("✅ Função normalizar_telefone existe")
                
                # Verificar se adiciona código do país
                if 'startswith(\'55\')' not in conteudo and 'startswith("55")' not in conteudo:
                    self.problemas.append({
                        'tipo': 'logica_incorreta',
                        'arquivo': 'routes/teams_suggest.py',
                        'funcao': 'normalizar_telefone',
                        'severidade': 'MÉDIO',
                        'mensagem': 'Função normalizar_telefone não verifica código do país 55'
                    })
                    print("⚠️ normalizar_telefone pode não adicionar código 55")
    
    def gerar_relatorio(self):
        """Gera relatório de problemas encontrados"""
        print("\n" + "="*60)
        print("📊 RELATÓRIO DE ANÁLISE")
        print("="*60 + "\n")
        
        if not self.problemas:
            print("✅ NENHUM PROBLEMA ENCONTRADO!\n")
            return
        
        # Agrupar por severidade
        criticos = [p for p in self.problemas if p['severidade'] == 'CRÍTICO']
        altos = [p for p in self.problemas if p['severidade'] == 'ALTO']
        medios = [p for p in self.problemas if p['severidade'] == 'MÉDIO']
        
        print(f"❌ CRÍTICOS: {len(criticos)}")
        print(f"⚠️  ALTOS: {len(altos)}")
        print(f"⚡ MÉDIOS: {len(medios)}")
        print(f"\n📋 TOTAL: {len(self.problemas)} problemas\n")
        
        # Detalhar problemas
        for i, problema in enumerate(self.problemas, 1):
            print(f"{i}. [{problema['severidade']}] {problema['tipo']}")
            print(f"   Mensagem: {problema['mensagem']}")
            if 'arquivo' in problema:
                print(f"   Arquivo: {problema['arquivo']}")
            if 'linha' in problema:
                print(f"   Linha: {problema['linha']}")
            print()

if __name__ == '__main__':
    analisador = AnalisadorAutonomo()
    sucesso = analisador.analisar_projeto_completo()
    analisador.gerar_relatorio()
    
    if not sucesso:
        print("🔧 Prosseguindo para FASE 2: CORREÇÃO AUTOMÁTICA...")