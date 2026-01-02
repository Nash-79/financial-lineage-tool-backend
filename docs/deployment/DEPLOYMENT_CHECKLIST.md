# Deployment Checklist

## Environment Variables
- [ ] `OLLAMA_HOST` is accessible from API container
- [ ] `QDRANT_HOST` is set correctly
- [ ] `REDIS_HOST` is set correctly
- [ ] `NEO4J_URI` is set correctly

## WebSocket Configuration
- [ ] Reverse proxy (Nginx/Traefik) supports WebSocket upgrade headers
- [ ] Connection timeout set > 60s for keepalive
- [ ] Sticky sessions enabled if using multiple API replicas (Note: broadcast currently local-only)

## Resources
- [ ] API Container memory limit > 1GB
- [ ] Qdrant volume persistence verified

## Verification
- [ ] `/health` returns 200 OK
- [ ] WebSocket connection to `/api/v1/ws/dashboard` succeeds
- [ ] Admin restart endpoint `/admin/restart` triggers reload
