# WowMCP Bridge Starter for Windows

Write-Host "=== WowMCP Bridge Starting ===" -ForegroundColor Green

# 1. Check for Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Error: Python not found. Please install Python 3.11+." -ForegroundColor Red
    Pause
    Exit
}

# 2. Check for dependencies
Write-Host "[*] Checking dependencies..."
python -m pip install -r bridge/requirements.txt --quiet

# 3. Check for API key
if (!($env:WOW_MCP_API_KEY)) {
    Write-Host "[!] Warning: WOW_MCP_API_KEY not set. OpenAI/Anthropic won't work." -ForegroundColor Yellow
    Write-Host "[*] You can set it with: setx WOW_MCP_API_KEY 'your-key-here'" -ForegroundColor Cyan
}

# 4. Run the Bridge
Write-Host "[*] Starting Bridge daemon..."
$env:PYTHONPATH = "mcp-server;bridge"
python bridge/main.py
