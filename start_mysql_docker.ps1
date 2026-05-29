# MySQL Docker 启动脚本
# 创建本地MySQL 8.0容器并初始化数据库

param(
    [string]$ContainerName = "hpc-mysql",
    [int]$Port = 3306,
    [string]$RootPassword = "hpc_root_123456",
    [string]$DatabaseName = "hpc",
    [string]$DataDir = "$PSScriptRoot\mysql_data",
    [string]$SqlFile = "$PSScriptRoot\docs\db.sql"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HPC MySQL Docker 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查Docker是否安装
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "错误: Docker 未安装或未添加到PATH环境变量"
    exit 1
}

# 检查Docker是否运行
try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "错误: Docker 服务未运行，请先启动Docker Desktop"
        exit 1
    }
} catch {
    Write-Error "错误: 无法连接到Docker服务"
    exit 1
}

Write-Host "[✓] Docker 服务正常" -ForegroundColor Green

# 创建数据目录
if (!(Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Host "[✓] 创建数据目录: $DataDir" -ForegroundColor Green
} else {
    Write-Host "[✓] 数据目录已存在: $DataDir" -ForegroundColor Green
}

# 创建初始化脚本目录
$initDir = "$DataDir\docker-entrypoint-initdb.d"
if (!(Test-Path $initDir)) {
    New-Item -ItemType Directory -Path $initDir -Force | Out-Null
}

# 复制SQL文件到初始化目录
if (Test-Path $SqlFile) {
    Copy-Item -Path $SqlFile -Destination "$initDir\01_init.sql" -Force
    Write-Host "[✓] 复制SQL初始化文件" -ForegroundColor Green
} else {
    Write-Warning "警告: SQL文件不存在: $SqlFile"
    # 创建一个空的初始化文件
    "-- 初始化脚本占位符" | Out-File -FilePath "$initDir\01_init.sql" -Encoding UTF8
}

# 检查容器是否已存在
$existingContainer = docker ps -a --filter "name=$ContainerName" --format "{{.Names}}"

if ($existingContainer -eq $ContainerName) {
    Write-Host "[!] 容器 '$ContainerName' 已存在" -ForegroundColor Yellow
    
    # 检查容器是否正在运行
    $runningContainer = docker ps --filter "name=$ContainerName" --format "{{.Names}}"
    
    if ($runningContainer -eq $ContainerName) {
        Write-Host "[✓] 容器正在运行" -ForegroundColor Green
    } else {
        Write-Host "[*] 启动已存在的容器..." -ForegroundColor Cyan
        docker start $ContainerName
        if ($LASTEXITCODE -ne 0) {
            Write-Error "错误: 无法启动容器"
            exit 1
        }
        Write-Host "[✓] 容器已启动" -ForegroundColor Green
    }
} else {
    Write-Host "[*] 创建新的MySQL容器..." -ForegroundColor Cyan
    
    docker run -d `
        --name $ContainerName `
        -e MYSQL_ROOT_PASSWORD=$RootPassword `
        -e MYSQL_DATABASE=$DatabaseName `
        -p ${Port}:3306 `
        -v "${DataDir}:/var/lib/mysql" `
        -v "${initDir}:/docker-entrypoint-initdb.d" `
        --restart unless-stopped `
        mysql:8.0 `
        --character-set-server=utf8mb4 `
        --collation-server=utf8mb4_unicode_ci
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "错误: 创建容器失败"
        exit 1
    }
    
    Write-Host "[✓] 容器创建成功" -ForegroundColor Green
    
    # 等待MySQL启动
    Write-Host "[*] 等待MySQL初始化 (约30秒)..." -ForegroundColor Cyan
    Start-Sleep -Seconds 30
}

# 显示连接信息
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  MySQL 连接信息" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  主机:     127.0.0.1" -ForegroundColor White
Write-Host "  端口:     $Port" -ForegroundColor White
Write-Host "  数据库:   $DatabaseName" -ForegroundColor White
Write-Host "  用户名:   root" -ForegroundColor White
Write-Host "  密码:     $RootPassword" -ForegroundColor White
Write-Host ""
Write-Host "  DSN连接字符串:" -ForegroundColor Yellow
Write-Host "  mysql+pymysql://root:${RootPassword}@127.0.0.1:${Port}/${DatabaseName}?charset=utf8mb4" -ForegroundColor Gray
Write-Host ""
Write-Host "  常用命令:" -ForegroundColor Yellow
Write-Host "  - 停止:   docker stop $ContainerName" -ForegroundColor Gray
Write-Host "  - 启动:   docker start $ContainerName" -ForegroundColor Gray
Write-Host "  - 删除:   docker rm -f $ContainerName" -ForegroundColor Gray
Write-Host "  - 日志:   docker logs $ContainerName" -ForegroundColor Gray
Write-Host "  - 进入:   docker exec -it $ContainerName mysql -uroot -p" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

# 更新config.ini
$configFile = "$PSScriptRoot\config.ini"
if (Test-Path $configFile) {
    Write-Host "[*] 更新配置文件..." -ForegroundColor Cyan
    
    $configContent = Get-Content $configFile -Raw -Encoding UTF8
    
    # 更新MySQL连接字符串
    $newDsn = "mysql+pymysql://root:${RootPassword}@127.0.0.1:${Port}/${DatabaseName}?charset=utf8mb4"
    
    if ($configContent -match "dsn=.*") {
        $configContent = $configContent -replace "dsn=.*", "dsn=$newDsn"
    } else {
        $configContent += "`n[mysql]`n" + "dsn=$newDsn"
    }
    
    # 添加auth配置
    if ($configContent -notmatch "\[auth\]") {
        $configContent += "`n`n[auth]`n" + "port=8051`n" + "secret_key=hpc-dashboard-secret-key-change-in-production"
    }
    
    $configContent | Out-File -FilePath $configFile -Encoding UTF8
    Write-Host "[✓] 配置文件已更新: $configFile" -ForegroundColor Green
}

Write-Host ""
Write-Host "[✓] MySQL Docker 启动完成!" -ForegroundColor Green
