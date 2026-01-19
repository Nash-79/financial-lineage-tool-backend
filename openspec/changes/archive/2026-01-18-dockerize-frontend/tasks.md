
1. Create `financial-lineage-tool-frontend/Dockerfile` with multi-stage build (Node build -> Nginx serve).
2. Create `financial-lineage-tool-frontend/nginx.conf` with reverse proxy rules for `/api` and `/health`.
3. Update `financial-lineage-tool-backend/docker-compose.yml` to include the `frontend` service.
4. Verify the stack starts with `docker-compose up` and frontend is accessible at `http://localhost:3000`.
