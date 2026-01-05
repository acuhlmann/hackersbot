#!/usr/bin/env bash

# Deploy HackersBot app to GCP VM using Docker
# This script builds the Docker image locally, pushes it to the VM, and runs it

ZONE=${ZONE:-asia-east2-a}
INSTANCE=${INSTANCE:-main}
PROJECT=${PROJECT:-photogroup-215600}
IMAGE_NAME=hackersbot
CONTAINER_NAME=hackersbot-app

# LLM configuration (can be set via environment variables)
# If not set, will default to 'auto' which tries Ollama first, then Deepseek
LLM_PROVIDER=${LLM_PROVIDER:-auto}
DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-}

echo "Deploying HackersBot app to GCP VM using Docker..."
echo "Project: $PROJECT"
echo "Instance: $INSTANCE"
echo "Zone: $ZONE"
echo ""

# Verify instance exists
if ! gcloud compute instances describe $INSTANCE --project $PROJECT --zone $ZONE &>/dev/null; then
    echo "ERROR: VM instance '$INSTANCE' not found in project '$PROJECT' zone '$ZONE'"
    exit 1
fi

# Function to run gcloud commands and ignore metadata update warnings
run_gcloud_ssh() {
    local cmd="$1"
    local description="$2"
    local allow_failure="${3:-false}"  # Third parameter: allow failure (default: false)
    local temp_output
    local exit_code
    
    # Run command, capture both output and exit code
    temp_output=$(gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command "$cmd" 2>&1)
    exit_code=$?
    
    # Filter out metadata warnings but keep everything else
    filtered_output=$(echo "$temp_output" | grep -v "^Updating project ssh metadata\.\.\." | grep -v "^Updating instance ssh metadata\.\.\." | grep -v "^\.$" | grep -v "^done\.$" || true)
    
    # Show filtered output if there's content
    if [ -n "$filtered_output" ]; then
        echo "$filtered_output"
    fi
    
    if [ $exit_code -ne 0 ]; then
        if [ "$allow_failure" != "true" ]; then
            echo "ERROR: $description failed (exit code: $exit_code)" >&2
            if [ -n "$temp_output" ] && [ "$filtered_output" != "$temp_output" ]; then
                echo "Full command output:" >&2
                echo "$temp_output" >&2
            fi
            return $exit_code
        fi
        # Failure is allowed - return 0 so GitHub Actions doesn't mark it as failed
        # The exit code is non-zero but we're treating it as informational
        return 0
    fi
    return 0
}

# Check if Docker is installed on VM, install if not
echo "Checking Docker installation on VM..."
if ! run_gcloud_ssh "docker --version" "Checking Docker" >/dev/null 2>&1; then
    echo "Docker is not installed on the VM. Installing Docker..."
    run_gcloud_ssh "curl -fsSL https://get.docker.com | sudo sh && sudo systemctl enable docker && sudo systemctl start docker" "Installing Docker" || {
        echo "ERROR: Failed to install Docker on the VM"
        exit 1
    }
    echo "Docker installed successfully."
else
    echo "Docker is already installed."
fi

# Check disk space on VM
echo "Checking disk space on VM..."
run_gcloud_ssh "
    echo 'Current disk usage:'
    df -h /
    echo ''
    echo 'Docker disk usage:'
    sudo docker system df 2>/dev/null || echo 'Unable to check Docker disk usage'
" "Checking disk space" || true

# Build Docker image locally
echo "Building Docker image locally..."
if ! docker build -t $IMAGE_NAME:latest .; then
    echo "ERROR: Failed to build Docker image"
    exit 1
fi

# Check VM disk space BEFORE load (informational; streaming upload avoids VM /tmp tarball)
echo "Checking VM disk space before image load..."
run_gcloud_ssh "
    echo 'Current disk usage:'
    df -h /
    echo ''
    echo 'Docker disk usage:'
    sudo docker system df 2>/dev/null || echo 'Unable to check Docker disk usage'
" "Checking VM disk space" || true

# If disk is extremely low, attempt cleanup (but do not fail early; docker load will be the source of truth)
VM_AVAIL_ROOT_MB=$(run_gcloud_ssh "df -m / | tail -1 | awk '{print \$4}'" "Checking root free space" "true" | tail -n 1 | tr -d '\r' || true)
if [[ -n "$VM_AVAIL_ROOT_MB" ]] && [[ "$VM_AVAIL_ROOT_MB" =~ ^[0-9]+$ ]] && [ "$VM_AVAIL_ROOT_MB" -lt 300 ]; then
    echo "Low free space detected on VM (${VM_AVAIL_ROOT_MB}MB). Attempting cleanup..."
    run_gcloud_ssh "
        sudo docker stop $CONTAINER_NAME 2>/dev/null || true
        sudo docker rm $CONTAINER_NAME 2>/dev/null || true
        sudo docker system prune -af || true
        sudo docker volume prune -f || true
        echo ''
        echo 'Disk space after cleanup:'
        df -h / | tail -1
    " "Cleaning up old Docker resources" || true
fi

# Stream Docker image to VM and load it (no tar file on VM)
echo "Streaming Docker image to VM and loading it (no /tmp tarball)..."
LOAD_OUTPUT=$(docker save $IMAGE_NAME:latest | gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command "sudo docker load" -- -T 2>&1)
LOAD_EXIT_CODE=$?

if [ $LOAD_EXIT_CODE -ne 0 ]; then
    echo "=== IMAGE LOAD FAILED ==="
    echo "Exit code: $LOAD_EXIT_CODE"
    echo "Output:"
    echo "$LOAD_OUTPUT"
    echo "========================="
    echo ""
    echo "Attempting aggressive cleanup on VM and retrying image load..."
    run_gcloud_ssh "
        sudo docker stop $CONTAINER_NAME 2>/dev/null || true
        sudo docker rm $CONTAINER_NAME 2>/dev/null || true
        sudo docker system prune -af || true
        sudo docker volume prune -f || true
        echo ''
        echo 'Disk space after cleanup:'
        df -h / | tail -1
        echo ''
        echo 'Docker disk usage after cleanup:'
        sudo docker system df 2>/dev/null || true
    " "Aggressive cleanup" || true

    LOAD_OUTPUT=$(docker save $IMAGE_NAME:latest | gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command "sudo docker load" -- -T 2>&1)
    LOAD_EXIT_CODE=$?
    if [ $LOAD_EXIT_CODE -ne 0 ]; then
        echo "=== IMAGE LOAD RETRY FAILED ==="
        echo "Exit code: $LOAD_EXIT_CODE"
        echo "Output:"
        echo "$LOAD_OUTPUT"
        echo "==============================="
        exit 1
    fi
fi

echo "$LOAD_OUTPUT"
echo "Image loaded successfully on VM."

# Build docker run command with environment variables
DOCKER_RUN_CMD="docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p 127.0.0.1:18080:8000 \
    -e PORT=8000 \
    -e BIND_ADDRESS=0.0.0.0 \
    -e PYTHONUNBUFFERED=1"

# Add LLM provider environment variable if set
if [ -n "$LLM_PROVIDER" ]; then
    DOCKER_RUN_CMD="$DOCKER_RUN_CMD -e LLM_PROVIDER=$LLM_PROVIDER"
fi

# Add Deepseek API key if set (for cloud LLM)
if [ -n "$DEEPSEEK_API_KEY" ]; then
    DOCKER_RUN_CMD="$DOCKER_RUN_CMD -e DEEPSEEK_API_KEY=$DEEPSEEK_API_KEY"
fi

DOCKER_RUN_CMD="$DOCKER_RUN_CMD $IMAGE_NAME:latest"

# Run container on VM
echo ""
echo "=== Loading Image and Starting Container ==="
run_gcloud_ssh "
    # Stop and remove existing container if it exists
    echo 'Stopping existing container (if any)...'
    sudo docker stop $CONTAINER_NAME 2>/dev/null || true
    sudo docker rm $CONTAINER_NAME 2>/dev/null || true
    
    # Kill any processes on port 18080 in case they're running outside Docker
    sudo lsof -ti:18080 | xargs sudo kill -9 2>/dev/null || true
    
    # Run the new container
    # Bind to 127.0.0.1 so nginx can reach it (not exposed publicly)
    echo 'Starting new container...'
    if ! sudo $DOCKER_RUN_CMD; then
        echo 'ERROR: Failed to start container'
        exit 1
    fi
    
    # Wait a moment for container to start
    sleep 2
    
    # Verify container is running
    if ! sudo docker ps | grep -q $CONTAINER_NAME; then
        echo 'ERROR: Container failed to start'
        echo 'Container logs:'
        sudo docker logs $CONTAINER_NAME 2>&1 || true
        exit 1
    fi
    
    # Check container health
    echo 'Checking container health...'
    sleep 3
    if sudo docker inspect $CONTAINER_NAME --format='{{.State.Health.Status}}' 2>/dev/null | grep -q unhealthy; then
        echo 'WARNING: Container is unhealthy. Check logs below.'
    fi
" "Deploying Docker container" || exit 1

echo ""
echo "✅ Docker deployment completed successfully!"
echo ""
echo "=== Container Status ==="
run_gcloud_ssh "sudo docker ps --filter name=$CONTAINER_NAME --format 'table {{.ID}}\t{{.Image}}\t{{.Command}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}'" "Checking container status" "true" || true
echo ""
echo "=== Container Logs (last 20 lines) ==="
run_gcloud_ssh "sudo docker logs --tail 20 $CONTAINER_NAME 2>&1" "Viewing container logs" "true" || true
echo ""
echo "The app should be available at: https://hackernews.photogroup.network"
echo ""
echo "To view logs: gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command 'sudo docker logs -f $CONTAINER_NAME'"
echo "To restart: gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command 'sudo docker restart $CONTAINER_NAME'"

