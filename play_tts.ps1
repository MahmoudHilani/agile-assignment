param(
    [string]$question = "What is artificial intelligence?"
)

# Clean old chunk files
Remove-Item "C:\Users\UMESH VARMA\Downloads\chunk_*.mp3" -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Users\UMESH VARMA\Downloads\full_answer.mp3" -Force -ErrorAction SilentlyContinue

Write-Host "Asking: $question" -ForegroundColor Cyan

$response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ask/stream" `
    -Method POST `
    -Headers @{"Content-Type"="application/json"} `
    -Body "{`"text`": `"$question`"}" `
    -UseBasicParsing

$text = [System.Text.Encoding]::UTF8.GetString($response.RawContentStream.ToArray())
$lines = ($text -split "`n") | Where-Object { $_ -ne "" }

Write-Host "Received $($lines.Count) audio chunks - merging..." -ForegroundColor Green

$allBytes = @()
foreach ($line in $lines) {
    $json = $line | ConvertFrom-Json
    $bytes = [Convert]::FromBase64String($json.audio_b64)
    $allBytes += $bytes
}

$path = "C:\Users\UMESH VARMA\Downloads\full_answer.mp3"
[System.IO.File]::WriteAllBytes($path, $allBytes)
Write-Host "Playing merged audio..." -ForegroundColor Green
Invoke-Expression "start '$path'"
Write-Host "Done!" -ForegroundColor Green