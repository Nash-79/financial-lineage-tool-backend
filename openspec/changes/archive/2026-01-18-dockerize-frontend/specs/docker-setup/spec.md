# Spec Delta: Docker Setup

## ADDED Requirements

### Requirement: Frontend Containerization
The frontend application MUST be containerized using a multi-stage Dockerfile that builds the static assets and serves them using Nginx.

#### Scenario: Multi-stage Build
Given the frontend source code
When the Docker image is built
Then it should first compile the React app using Node.js
And then copy the artifacts to an Nginx image for serving
And the final image size should be optimized (no node_modules).

### Requirement: Nginx Reverse Proxy
The frontend container MUST use Nginx to serve the application and reverse-proxy API requests to the backend service.

#### Scenario: API Proxying
Given a running frontend container
When a request is made to `/api/*` (e.g., `/api/v1/health`)
Then Nginx should forward the request to `http://api:8000/api/*`
And return the response to the client
And CORS headers should be handled correctly.

#### Scenario: SPA Routing
Given a running frontend container
When a request is made to a non-root route (e.g., `/settings`)
Then Nginx should serve `index.html`
And let the React router handle the view rendering.

### Requirement: Docker Compose Integration
The frontend service MUST be included in the backend's `docker-compose.yml` to allow starting the full stack with a single command.

#### Scenario: Unified Startup
Given the `docker-compose.yml` file
When `docker-compose up` is run
Then both `api` and `frontend` services should start
And the frontend should be accessible at `http://localhost:3000`
And the frontend should be able to communicate with the `api` service via the internal Docker network.
