# Legacy Startup Scripts

## ⚠️ DEPRECATED

The scripts in this directory are **deprecated** and kept only for reference.

### Deprecated Scripts

- **start-local.bat** - Manual local startup (Windows)
- **start-simple.bat** - Simple local startup (Windows)

### Why Deprecated?

These scripts were used for manual local setup before Docker Compose was adopted as the primary deployment method. They are no longer maintained and may not work with current configuration.

### Recommended Alternative

**Use Docker Compose instead:**

```bash
# Windows
start-docker.bat

# Unix/Linux/macOS
./start-docker.sh
```

### Benefits of Docker Compose

1. **Automatic service orchestration** - All services start together
2. **Health checks and dependencies** - Services wait for dependencies
3. **Easier debugging** - Isolated containers with logs
4. **Production-ready** - Same environment locally and in production
5. **No manual dependency installation** - Everything in containers

### Migration Guide

If you were using these scripts:

1. **Stop any running services** started with legacy scripts
2. **Install Docker Desktop** from https://www.docker.com/products/docker-desktop
3. **Run the check script** to validate your environment:
   ```bash
   check-docker.bat  # Windows
   ./check-docker.sh # Unix/Linux/macOS
   ```
4. **Start with Docker**:
   ```bash
   start-docker.bat  # Windows
   ./start-docker.sh # Unix/Linux/macOS
   ```

### Documentation

- [Docker Setup Guide](../../docs/setup/DOCKER_SETUP.md) - Complete Docker deployment guide
- [Getting Started](../../docs/setup/GETTING_STARTED.md) - Quick start guide
- [Docker Troubleshooting](../../docs/setup/DOCKER_TROUBLESHOOTING.md) - Common Docker issues

### Last Supported Version

These scripts were last supported in version **1.0.0** (December 2025).

**Removal Timeline:** These scripts will be removed in version **2.0.0** (planned for Q2 2026).

---

**Need help?** See the [Docker Setup Guide](../../docs/setup/DOCKER_SETUP.md) or open an issue.
