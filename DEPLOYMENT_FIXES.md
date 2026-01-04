# Deployment Fixes for 502 Error

## Issues Found

1. **Container Conflict**: The deployment script wasn't stopping/removing the old container before starting a new one
2. **Missing Environment Variables**: LLM configuration (LLM_PROVIDER, DEEPSEEK_API_KEY) wasn't being passed to the container
3. **LLM Connection Error**: The app was trying to connect to Ollama (not available in container) instead of using Deepseek

## Fixes Applied

### 1. Container Management
- Added code to stop and remove existing container before starting new one
- Added health check verification after container starts
- Added better error messages

### 2. Environment Variables
- Added support for `LLM_PROVIDER` environment variable
- Added support for `DEEPSEEK_API_KEY` environment variable
- These are now passed to the Docker container

### 3. Startup Robustness
- Made index generation more robust (won't fail if summaries directory is empty)
- Better error handling during startup

## How to Deploy with Correct Configuration

### Option 1: Set Environment Variables Before Running deploy-docker.sh

```bash
export LLM_PROVIDER=deepseek
export DEEPSEEK_API_KEY=your-api-key-here
./deploy-docker.sh
```

### Option 2: Use GitHub Actions Secrets

If deploying via GitHub Actions, add these secrets:
- `LLM_PROVIDER` (set to `deepseek`)
- `DEEPSEEK_API_KEY` (your Deepseek API key)

Then update your GitHub Actions workflow to pass these to the deployment script.

### Option 3: Manual Container Restart with Environment Variables

If the container is already running, you can restart it with the correct environment:

```bash
# SSH into the VM
gcloud compute ssh main --project photogroup-215600 --zone asia-east2-a

# Stop and remove old container
sudo docker stop hackersbot-app
sudo docker rm hackersbot-app

# Run new container with environment variables
sudo docker run -d \
    --name hackersbot-app \
    --restart unless-stopped \
    -p 127.0.0.1:18080:8000 \
    -e PORT=8000 \
    -e BIND_ADDRESS=0.0.0.0 \
    -e PYTHONUNBUFFERED=1 \
    -e LLM_PROVIDER=deepseek \
    -e DEEPSEEK_API_KEY=your-api-key-here \
    hackersbot:latest
```

## Verifying the Fix

After deployment, check:

1. **Container is running**:
   ```bash
   gcloud compute ssh main --project photogroup-215600 --zone asia-east2-a --command 'sudo docker ps | grep hackersbot-app'
   ```

2. **Container logs** (should not show connection errors):
   ```bash
   gcloud compute ssh main --project photogroup-215600 --zone asia-east2-a --command 'sudo docker logs --tail 50 hackersbot-app'
   ```

3. **Health check**:
   ```bash
   gcloud compute ssh main --project photogroup-215600 --zone asia-east2-a --command 'curl -I http://127.0.0.1:18080/'
   ```

4. **Check website**: https://hackernews.photogroup.network should load without 502 error

## Troubleshooting

If you still get 502 errors:

1. **Check nginx/caddy configuration** - Make sure it's proxying to `127.0.0.1:18080`
2. **Check container logs** - Look for startup errors
3. **Check container health** - `sudo docker inspect hackersbot-app | grep -A 10 Health`
4. **Verify port binding** - `sudo docker port hackersbot-app` should show `8000/tcp -> 127.0.0.1:18080`

