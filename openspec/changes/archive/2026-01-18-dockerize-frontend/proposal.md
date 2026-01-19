# Proposal: Dockerize Frontend

## Objective
Containerize the frontend application and integrate it with the existing backend Docker setup to provide a unified local development environment.

## Context
Currently, the backend (Lineage API, Qdrant, Redis) runs in Docker, but the frontend runs separately on the host via `npm run dev`. This creates friction in setup and doesn't match a production-like environment. Dockerizing the frontend ensures consistency and simplifies the "up" command.

## Goals
- Create a multi-stage Dockerfile for the frontend (Build -> Nginx).
- Add the frontend service to the backend `docker-compose.yml`.
- Configure Nginx to reverse-proxy `/api` requests to the backend container, eliminating CORS configuration complexity for the Docker environment.
- Ensure the frontend is accessible at `http://localhost:3000`.

## Non-Goals
- Cloud deployment configuration (this is strictly for local dev/Docker).
- Changing the frontend build tool (Vite remains).

## Trade-offs
- **Nginx Proxy vs Custom Vite Config**: Using Nginx is more production-like and handles routing rules cleanly. Configuring Vite to proxy in Docker is possible but less robust for a static build artifact.
- **Port 3000**: Standard React port, avoids conflict with backend (8000).
