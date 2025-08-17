# PowerShell script to clean up server processes and free port 3000
Write-Host "🔧 Cleaning up server processes and freeing port 3000..." -ForegroundColor Yellow

# Kill any Python processes running server_fastapi.py
Write-Host "📋 Looking for server_fastapi.py processes..." -ForegroundColor Cyan
$serverProcesses = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq "python" }
$killedCount = 0

foreach ($proc in $serverProcesses) {
    try {
        $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId = $($proc.Id)").CommandLine
        if ($cmdline -and $cmdline.Contains("server_fastapi.py")) {
            Write-Host "🔄 Terminating server process (PID: $($proc.Id))..." -ForegroundColor Yellow
            Stop-Process -Id $proc.Id -Force
            $killedCount++
            Start-Sleep -Seconds 1
        }
    }
    catch {
        Write-Host "⚠️ Could not check process $($proc.Id): $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "✅ Killed $killedCount server processes" -ForegroundColor Green

# Kill processes using port 3000
Write-Host "📋 Looking for processes using port 3000..." -ForegroundColor Cyan
try {
    $netstat = netstat -ano | Select-String ":3000.*LISTENING"
    if ($netstat) {
        foreach ($line in $netstat) {
            $parts = $line -split '\s+'
            if ($parts.Length -ge 5) {
                $processId = $parts[-1]
                Write-Host "🔄 Killing process (PID: $processId) using port 3000..." -ForegroundColor Yellow
                try {
                    Stop-Process -Id $processId -Force
                    Write-Host "✅ Killed process $processId" -ForegroundColor Green
                    Start-Sleep -Seconds 1
                }
                catch {
                    Write-Host "⚠️ Failed to kill process $processId`: $($_.Exception.Message)" -ForegroundColor Red
                }
            }
        }
    }
    else {
        Write-Host "ℹ️ No processes found using port 3000" -ForegroundColor Blue
    }
}
catch {
    Write-Host "⚠️ Error checking port 3000: $($_.Exception.Message)" -ForegroundColor Red
}

# Wait a moment for processes to fully terminate
Start-Sleep -Seconds 2

# Check if port 3000 is now free
Write-Host "🔍 Checking if port 3000 is now available..." -ForegroundColor Cyan
try {
    $testSocket = New-Object System.Net.Sockets.TcpClient
    $result = $testSocket.BeginConnect("localhost", 3000, $null, $null)
    $success = $result.AsyncWaitHandle.WaitOne(1000, $false)
    $testSocket.Close()
    
    if ($success) {
        Write-Host "⚠️ Port 3000 is still in use" -ForegroundColor Red
    }
    else {
        Write-Host "✅ Port 3000 is now available" -ForegroundColor Green
    }
}
catch {
    Write-Host "✅ Port 3000 is available (connection failed as expected)" -ForegroundColor Green
}

Write-Host "🎉 Cleanup completed!" -ForegroundColor Green 