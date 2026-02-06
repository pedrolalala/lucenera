import sys
import subprocess

def run_command(cmd, descricao):
    print(f"\n{'='*60}")
    print(f"🔄 {descricao}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, shell=True, capture_output=False, text=True)
    return result.returncode == 0

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║     SISTEMA DE TESTE AUTOMATIZADO E AUTO-CORREÇÃO          ║
║              Endpoint: /teams/suggest                      ║
╚════════════════════════════════════════════════════════════╝
    """)
    resultados = {}
    resultados['setup'] = run_command(
        'python tests/test_setup.py',
        'FASE 1: Validação de Setup e Ambiente'
    )
    if not resultados['setup']:
        print("\n❌ FASE 1 FALHOU - Corrija problemas de setup antes de continuar")
        return
    resultados['unit'] = run_command(
        'python tests/test_unit.py',
        'FASE 2: Testes Unitários'
    )
    if not resultados['unit']:
        print("\n⚠️  FASE 2 FALHOU - Tentando correção automática...")
        run_command('python tests/auto_fix.py', 'Aplicando Auto-Fix')
        print("\n🔄 Re-executando testes unitários...")
        resultados['unit_retry'] = run_command(
            'python tests/test_unit.py',
            'FASE 2 (Retry): Testes Unitários'
        )
        if not resultados['unit_retry']:
            print("\n❌ Correção automática não resolveu. Revisão manual necessária.")
            return
    resultados['integration'] = run_command(
        'python tests/test_integration.py',
        'FASE 3: Testes de Integração'
    )
    print("\n⚠️  ATENÇÃO: Certifique-se que o servidor Flask está rodando!")
    resposta = input("Servidor Flask rodando? (s/n): ")
    if resposta.lower() == 's':
        resultados['e2e'] = run_command(
            'python tests/test_e2e.py',
            'FASE 4: Testes End-to-End'
        )
    else:
        print("\n⚠️  Testes E2E pulados - inicie servidor com: python app.py")
        resultados['e2e'] = None
    print(f"\n\n{'='*60}")
    print("📊 RELATÓRIO FINAL DE TESTES")
    print(f"{'='*60}\n")
    for fase, resultado in resultados.items():
        if resultado is None:
            status = "⏭️  PULADO"
        elif resultado:
            status = "✅ PASSOU"
        else:
            status = "❌ FALHOU"
        print(f"{status}  - {fase.upper()}")
    total = sum(1 for r in resultados.values() if r is not None)
    passou = sum(1 for r in resultados.values() if r == True)
    print(f"\n{'='*60}")
    print(f"RESULTADO GERAL: {passou}/{total} fases passaram")
    if passou == total:
        print("🎉 TODOS OS TESTES PASSARAM! Sistema funcionando 100%")
    else:
        print("⚠️  Alguns testes falharam. Revise os logs acima.")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
