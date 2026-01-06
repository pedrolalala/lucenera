# Run approval test: check /ping, start server if needed, then call /teams/approve and save response
try {
    $r = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/ping' -Method GET -TimeoutSec 3 -ErrorAction Stop
    Write-Host 'PING_OK'
    $r | ConvertTo-Json -Depth 2 | Out-File -FilePath tools/ping_result.json -Encoding utf8
} catch {
    Write-Host 'PING_FAIL — iniciando main.py'
    $py = Resolve-Path .\.venv\Scripts\python.exe
    Start-Process -FilePath $py -ArgumentList '.\main.py' -WorkingDirectory (Get-Location).Path -PassThru | Out-Null
    Start-Sleep -Seconds 4
}

try {
    $url = "http://127.0.0.1:5000/teams/approve?id=17137&token=troque_por_seu_token_aqui"
    Write-Host "Calling: $url"
    $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -Method GET -TimeoutSec 30 -ErrorAction Stop
    Write-Host "APPROVE_STATUS=$($resp.StatusCode)"
    $resp.Content | Out-File -FilePath approval_result.html -Encoding utf8
    Write-Host 'Saved approval_result.html'
} catch {
    Write-Host 'APPROVE_FAILED' $_.Exception.Message
}
