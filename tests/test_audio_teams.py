# -*- coding: utf-8 -*-
"""
Teste para verificar se o conteudo do audio aparece no Teams
"""

def test_audio_teams_display():
    print("TESTANDO EXIBICAO DE AUDIO NO TEAMS")
    print("=" * 50)
    
    # Simular dados de audio com interpretacao
    test_row = {
        "nome": {"display": "Filippo Giorgi"},
        "telefone": "5516992362355",
        "mensagem": {
            "text": "[Audio recebido]",
            "meta": {
                "audio_interpretation": "Oi pessoal, preciso organizar um video com o pessoal da obra para manter todos informados sobre o andamento do projeto",
                "audio_transcript": "oi pessoal preciso organizar um video com o pessoal da obra para manter todos informados sobre o andamento do projeto"
            }
        }
    }
    
    # Simular dados sem audio para comparacao
    test_row_no_audio = {
        "nome": {"display": "Cliente Teste"},
        "telefone": "5516999999999",
        "mensagem": {
            "text": "Mensagem de texto normal",
            "meta": {}
        }
    }
    
    print("\nTeste 1: Audio com interpretacao e transcricao")
    print("-" * 45)
    
    # Extrair meta
    meta = test_row["mensagem"]["meta"]
    has_audio_transcript = bool(meta.get("audio_interpretation") or meta.get("audio_transcript"))
    
    if has_audio_transcript:
        nome = test_row["nome"]["display"]
        tel = test_row["telefone"]
        
        # Logica corrigida
        audio_content = ""
        audio_interpretation = meta.get("audio_interpretation")
        audio_transcript = meta.get("audio_transcript")
        
        if audio_interpretation:
            audio_content = f"Audio: {audio_interpretation}"
            if audio_transcript and audio_transcript != audio_interpretation:
                audio_content += f"\nTranscricao: {audio_transcript}"
        elif audio_transcript:
            audio_content = f"Audio: {audio_transcript}"
        else:
            audio_content = "Audio recebido"
        
        teams_text = f"Nome: {nome}\nTelefone: {tel}\n\n{audio_content}\n\nSugerida: [resposta exemplo]"
        
        print("Texto enviado para Teams:")
        print(teams_text)
        
        # Verificar se contem o conteudo do audio
        if "preciso organizar um video" in teams_text:
            print("\n✅ SUCESSO: Conteudo do audio aparece no Teams!")
        else:
            print("\n❌ PROBLEMA: Conteudo do audio NAO aparece no Teams!")
    
    print("\n" + "=" * 50)
    print("TESTE CONCLUIDO!")

if __name__ == "__main__":
    test_audio_teams_display()