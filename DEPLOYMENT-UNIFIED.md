# Unified Deployment Guide for Fly.io

This guide deploys both backend and frontend as a single Fly.io application using Caddy as a reverse proxy.

## Prerequisites

1. Install Fly CLI:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. Login to Fly.io:
   ```bash
   fly auth login
   ```

## Deployment Steps

### 1. Create the Fly App

```bash
# From the root directory (where fly.toml is located)
fly launch --name conway-technical --region iad

# When prompted:
# - Say YES to setting up PostgreSQL
# - Say YES to setting up Redis (Upstash Redis)
# - Say YES to deploy now
```

### 2. Set up Redis (if not done during launch)

If you didn't set up Redis during launch, you can add it:

```bash
# Option A: Use Upstash Redis (recommended - serverless, free tier)
fly redis create --name conway-redis

# Option B: Deploy your own Redis instance
fly apps create conway-redis --region iad

cat > fly-redis.toml << 'EOF'
app = "conway-redis"
primary_region = "iad"

[build]
  image = "flyio/redis:7.2"

[[services]]
  internal_port = 6379
  protocol = "tcp"

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 256
EOF

fly deploy --app conway-redis --config fly-redis.toml
rm fly-redis.toml
```

### 3. Set Secrets

```bash
fly secrets set \
  GITHUB_TOKEN="your-github-personal-access-token" \
  OPENAI_API_KEY="your-openai-api-key" \
  JWT_SECRET="$(openssl rand -hex 32)" \
  REDIS_URL="redis://default@conway-redis.internal:6379" \
  PUBLIC_API_URL="https://conway-technical.fly.dev" \
  --app conway-technical
```

### 4. Deploy

```bash
# Deploy using the unified Dockerfile
fly deploy --dockerfile Dockerfile.unified
```

### 5. Scale if Needed

```bash
# Scale to 2 instances
fly scale count 2

# Or scale VM size
fly scale vm shared-cpu-2x --memory 1024
```

## URLs

Your application will be available at:
- Main URL: `https://conway-technical.fly.dev`
- API endpoints: `https://conway-technical.fly.dev/api/*`
- WebSocket: `wss://conway-technical.fly.dev/ws`

## Architecture

The unified deployment runs:
- **Caddy** on port 8080 as the main entry point
- **Backend** (FastAPI) on port 8000 internally
- **Frontend** (SvelteKit) on port 3000 internally

Caddy routes:
- `/api/*` → Backend
- `/ws` → Backend WebSocket
- Everything else → Frontend

## Monitoring

View logs:
```bash
fly logs --app conway-technical
```

Check status:
```bash
fly status --app conway-technical
```

SSH into the container:
```bash
fly ssh console --app conway-technical
```

## Environment Variables

The app uses these environment variables:
- `DATABASE_URL` - Automatically set by Fly when PostgreSQL is attached
- `REDIS_URL` - Set to `redis://default@conway-redis.internal:6379`
- `GITHUB_TOKEN` - Your GitHub Personal Access Token
- `OPENAI_API_KEY` - Optional, for AI summaries
- `JWT_SECRET` - Random secret for JWT signing
- `PUBLIC_API_URL` - The public URL of your app

## Troubleshooting

1. Check individual services:
   ```bash
   fly ssh console
   supervisorctl status
   ```

2. View specific service logs:
   ```bash
   fly ssh console
   supervisorctl tail -f backend
   supervisorctl tail -f frontend
   supervisorctl tail -f caddy
   ```

3. Test internal services:
   ```bash
   fly ssh console
   # Test backend
   curl http://localhost:8000/health
   # Test frontend
   curl http://localhost:3000
   ```

## Cost Optimization

Running as a single app:
- Uses only 1 Fly.io app slot instead of 2
- Shares resources between frontend and backend
- Reduces data transfer costs (internal communication)

Recommended VM size:
- Development: `shared-cpu-1x` with 512MB RAM
- Production: `shared-cpu-2x` with 1GB RAM