# HPC Dashboard 启动脚本
# 启动集成FastAPI认证的Dash应用

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HPC Dashboard 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 获取脚本所在目录
$scriptDir = $PSScriptRoot
Set-Location $scriptDir

# 检查Python环境
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "错误: Python 未安装或未添加到PATH环境变量"
    exit 1
}

Write-Host "[✓] Python 版本: $(python --version)" -ForegroundColor Green

# 检查依赖
Write-Host "[*] 检查依赖..." -ForegroundColor Cyan
$missingModules = @()

$requiredModules = @(
    "dash",
    "fastapi",
    "uvicorn",
    "pyjwt",
    "dash_bootstrap_components"
)

foreach ($module in $requiredModules) {
    try {
        $null = python -c "import $module" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $missingModules += $module
        }
    } catch {
        $missingModules += $module
    }
}

if ($missingModules.Count -gt 0) {
    Write-Host "[!] 缺少以下依赖模块: $($missingModules -join ', ')" -ForegroundColor Yellow
    Write-Host "[*] 正在安装依赖..." -ForegroundColor Cyan
    pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Error "依赖安装失败"
        exit 1
    }
}

Write-Host "[✓] 依赖检查完成" -ForegroundColor Green

# 启动应用
Write-Host ""
Write-Host "[*] 启动 HPC Dashboard..." -ForegroundColor Cyan

# 检查端口8050是否被占用
$portInUse = Get-NetTCPConnection -LocalPort 8050 -ErrorAction SilentlyContinue
if ($portInUse) {
    Write-Warning "端口 8050 已被占用，尝试关闭现有进程..."
    Get-Process -Id $portInUse.OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
}

Write-Host "[✓] 应用地址: http://127.0.0.1:8050" -ForegroundColor Green
Write-Host "[✓] 默认账号: admin / admin123" -ForegroundColor Green
Write-Host ""

# 直接运行应用
python main.py
