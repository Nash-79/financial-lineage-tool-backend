# Docker Desktop Troubleshooting Guide

## Problem: Docker Desktop keeps stopping/crashing

You're experiencing Docker Desktop instability on Windows. This is preventing Gremlin Server from running.

## Quick Diagnosis

Run this command to check Docker status:
```bash
docker ps
```

If you see: `failed to connect to the docker API` - Docker is not running.

## Common Causes & Solutions

### 1. Docker Desktop Not Fully Initialized

**Symptoms:**
- Docker seems to start then immediately fails
- Can't connect to Docker API

**Solution:**
- Open Docker Desktop from Start Menu
- Wait for the whale icon in system tray to stop animating
- Look for "Docker Desktop is running" tooltip
- Wait an additional 30 seconds after it says "running"

### 2. WSL 2 Backend Issues

**Symptoms:**
- Docker Desktop uses WSL 2 backend
- WSL might not be installed or configured

**Solution:**
```powershell
# Check WSL status
wsl --list --verbose

# If WSL is not installed:
wsl --install

# Update WSL
wsl --update

# Restart Docker Desktop after WSL is ready
```

### 3. Hyper-V Conflicts

**Symptoms:**
- Other virtualization software running (VirtualBox, VMware)
- Hyper-V not enabled

**Solution:**
```powershell
# Check if Hyper-V is enabled (run as Administrator)
Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V

# Enable Hyper-V if needed
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

### 4. Resource Constraints

**Symptoms:**
- System running low on RAM
- Docker Desktop crashes under load

**Solution:**
1. Close other applications
2. Docker Desktop → Settings → Resources
3. Reduce memory allocation to 2-4GB
4. Reduce CPU allocation to 2-4 cores
5. Apply & Restart

### 5. Docker Desktop Version Issues

**Solution:**
- Update Docker Desktop to latest version
- Or try stable version instead of edge version
- Download from: https://www.docker.com/products/docker-desktop

## Step-by-Step Recovery

### Method 1: Clean Restart

```bash
# 1. Completely quit Docker Desktop
# Right-click system tray icon → Quit Docker Desktop

# 2. Wait 30 seconds

# 3. Start Docker Desktop from Start Menu

# 4. Wait for full initialization (2-3 minutes)

# 5. Verify it's running
docker ps

# 6. Start services
cd financial-lineage-tool
docker compose -f docker-compose.local.yml up -d gremlin-server qdrant redis

# 7. Verify containers are running
docker ps
```

### Method 2: Reset Docker Desktop

```bash
# 1. Docker Desktop → Settings → Troubleshoot → Reset to factory defaults
# WARNING: This removes all containers and images

# 2. Restart computer

# 3. Start Docker Desktop

# 4. Pull images
docker pull tinkerpop/gremlin-server:3.7.0
docker pull qdrant/qdrant:latest
docker pull redis:7-alpine

# 5. Start services
cd financial-lineage-tool
docker compose -f docker-compose.local.yml up -d gremlin-server qdrant redis
```

### Method 3: Use Alternative (NetworkX)

**Your application already works without Docker!**

The API is designed with automatic fallback to NetworkX when Gremlin is unavailable.

**Current working setup:**
- API: ✓ Running
- Ollama: ✓ Running
- Graph: ✓ NetworkX (in-memory)
- Cost: ✓ $0.00

**To continue without Docker:**
```bash
# Just run the API
cd financial-lineage-tool
python src/api/main_local.py
```

The application automatically uses NetworkX when Gremlin Server isn't available.

## Testing Docker Health

### Quick Health Check Script

Save as `check_docker.bat`:
```batch
@echo off
echo Checking Docker Desktop health...
echo.

docker ps >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker is not running
    echo Please start Docker Desktop
    exit /b 1
)

echo [PASS] Docker API is accessible

docker run --rm hello-world >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Cannot run containers
    exit /b 1
)

echo [PASS] Can run containers

docker compose version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Docker Compose not available
    exit /b 1
)

echo [PASS] Docker Compose available
echo.
echo Docker Desktop is healthy!
```

Run it:
```bash
check_docker.bat
```

## When Docker Becomes Stable

Once Docker Desktop is stable and staying running:

```bash
# 1. Verify Docker is healthy
docker ps

# 2. Start services
cd financial-lineage-tool
docker compose -f docker-compose.local.yml up -d gremlin-server qdrant redis

# 3. Wait for Gremlin to initialize
timeout /t 15

# 4. Verify services
docker ps

# Should show:
# gremlin-server   Up X seconds
# qdrant           Up X seconds
# redis            Up X seconds

# 5. Kill old API
netstat -ano | findstr :8000
taskkill //F //PID <PID>

# 6. Start API
python src/api/main_local.py
```

Look for this in the output:
```
[+] Gremlin client connected successfully
[+] Connected to Gremlin Server
```

## Current Recommendation

**For now, use NetworkX (it's already working!):**

Your API is running successfully at http://localhost:8000 with:
- Ollama for LLM inference
- NetworkX for graph storage
- Zero Docker dependencies
- $0 cost

Test it:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

**When you have time to troubleshoot Docker:**
- Try the recovery methods above
- Check Docker Desktop logs
- Consider WSL 2 updates
- Ensure adequate system resources

## Getting Help

If Docker continues to fail:

1. **Check Docker Desktop logs:**
   - Docker Desktop → Troubleshoot → View logs

2. **Windows Event Viewer:**
   - Look for Docker-related errors

3. **Docker Community:**
   - https://forums.docker.com/

4. **System Information:**
   - Windows version (Win 10/11)
   - RAM available
   - CPU model
   - WSL version (`wsl --version`)

---

**Remember: Your application works perfectly without Docker using NetworkX!**

The Gremlin Server integration is optional for production-scale graphs. For local development and testing, NetworkX is ideal.
