#!/usr/bin/env python3
"""
SCRIPT DE CORREÇÃO AUTÔNOMA - FASE 3: VALIDAÇÃO E ITERAÇÃO
Valida correções e itera até sucesso total
"""

import subprocess
import sys
import time

class ValidadorIterativo:
    def __init__(self, max_iteracoes=5):
        self.max_iteracoes = max_iteracoes
        self.iteracao_atual = 0
        self.historico = []
        
    def loop_correcao_ate_sucesso(self):
        """Loop iterativo até todos os testes passarem"""
        print("\n🔄 FASE 3: VALIDAÇÃO E ITERAÇÃO\n")
        
        while self.iteracao_atual < self.max_iteracoes:
            self.iteracao_atual += 1
            print(f"\n{'='*60}")
            print(f"🔄 ITERAÇÃO {self.iteracao_atual}/{self.max_iteracoes}")
            print(f"{'='*60}\n")
            
            # ETAPA 1: Executar análise
            print("🔍 Executando análise...")
            from fase1_analise import AnalisadorAutonomo
            analisador = AnalisadorAutonomo()
            analise_ok = analisador.analisar_projeto_completo()
            
            if analise_ok:
                print("\n✅ Análise: SEM PROBLEMAS")
            else:
                print(f"\n⚠️  Análise: {len(analisador.problemas)} problemas detectados")
                
                # ETAPA 2: Aplicar correções
                print("\n🔧 Aplicando correções...")
                from fase2_correcao import CorretorAutonomo
                corretor = CorretorAutonomo(analisador.problemas)
                corretor.corrigir_todos_problemas()
                time.sleep(1)
                continue
            
            # ETAPA 3: Executar testes
            print("\n✅ Executando testes...")
            testes_ok = self.executar_testes()
            
            if testes_ok:
                print("\n" + "="*60)
                print("🎉 SUCESSO TOTAL! TODOS OS TESTES PASSARAM!")
                print("="*60)
                self.gerar_relatorio_final(sucesso=True)
                return True
            else:
                print("\n⚠️  Alguns testes falharam")
                print("\n🔧 Analisando falhas de teste...")
        print("\n" + "="*60)
        print(f"⚠️  LIMITE DE ITERAÇÕES ATINGIDO ({self.max_iteracoes})")
        print("="*60)
        self.gerar_relatorio_final(sucesso=False)
        return False
    
    def executar_testes(self):
        """Executa bateria de testes"""
        try:
            result = subprocess.run(
                [sys.executable, 'tests/run_all_tests.py'],
                capture_output=True,
                text=True,
                timeout=60
            )
            sucesso = result.returncode == 0
            self.historico.append({
                'iteracao': self.iteracao_atual,
                'testes_passaram': sucesso,
                'stdout': result.stdout,
                'stderr': result.stderr
            })
            return sucesso
        except subprocess.TimeoutExpired:
            print("⏰ Timeout ao executar testes")
            return False
        except Exception as e:
            print(f"❌ Erro ao executar testes: {e}")
            return False
    
    def gerar_relatorio_final(self, sucesso):
        """Gera relatório final de todo o processo"""
        relatorio = f"""
# 📊 RELATÓRIO FINAL - CORREÇÃO AUTÔNOMA

**Data**: {time.strftime('%Y-%m-%d %H:%M:%S')}
**Iterações executadas**: {self.iteracao_atual}
**Status final**: {'✅ SUCESSO' if sucesso else '⚠️ PARCIAL'}

---

## 🔄 HISTÓRICO DE ITERAÇÕES

"""
        for registro in self.historico:
            status = "✅ PASSOU" if registro['testes_passaram'] else "❌ FALHOU"
            relatorio += f"### Iteração {registro['iteracao']}: {status}\n\n"
        if sucesso:
            relatorio += """
---

## 🎉 RESULTADO FINAL

✅ **SISTEMA 100% FUNCIONAL!**

Todos os problemas foram corrigidos automaticamente e todos os testes passaram com sucesso.

### Próximos Passos:
1. Revisar correções aplicadas
2. Validar configurações manuais (se houver)
3. Testar manualmente o fluxo completo
4. Fazer deploy para ambiente de staging

"""
        else:
            relatorio += """
---

## ⚠️ RESULTADO FINAL

Sistema corrigido parcialmente. Alguns problemas podem requerer atenção manual.

### Próximos Passos:
1. Revisar logs de teste da última iteração
2. Identificar problemas não resolvidos
3. Aplicar correções manuais se necessário
4. Re-executar validação

"""
        with open('RELATORIO_CORRECAO_AUTONOMA.md', 'w', encoding='utf-8') as f:
            f.write(relatorio)
        print(f"\n📄 Relatório salvo: RELATORIO_CORRECAO_AUTONOMA.md\n")

if __name__ == '__main__':
    validador = ValidadorIterativo(max_iteracoes=5)
    validador.loop_correcao_ate_sucesso()