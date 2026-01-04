#!/usr/bin/env bash

# Deploy HackersBot app to GCP VM using Docker
# This script builds the Docker image locally, pushes it to the VM, and runs it

ZONE=${ZONE:-asia-east2-a}
INSTANCE=${INSTANCE:-main}
PROJECT=${PROJECT:-photogroup-215600}
IMAGE_NAME=hackersbot
CONTAINER_NAME=hackersbot-app

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
    local temp_output
    local exit_code
    
    # Run command, capture both output and exit code
    temp_output=$(gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command "$cmd" 2>&1)
    exit_code=$?
    
    # Filter out metadata warnings but keep everything else
    echo "$temp_output" | grep -v "^Updating project ssh metadata\.\.\." | grep -v "^Updating instance ssh metadata\.\.\." | grep -v "^\.$" | grep -v "^done\.$" || true
    
    if [ $exit_code -ne 0 ]; then
        echo "ERROR: $description failed (exit code: $exit_code)"
        return $exit_code
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

# Build Docker image locally
echo "Building Docker image locally..."
if ! docker build -t $IMAGE_NAME:latest .; then
    echo "ERROR: Failed to build Docker image"
    exit 1
fi

# Save Docker image to tar file
echo "Saving Docker image to tar file..."
TAR_FILE="/tmp/${IMAGE_NAME}.tar"
docker save $IMAGE_NAME:latest -o "$TAR_FILE"

if [ ! -f "$TAR_FILE" ]; then
    echo "ERROR: Failed to save Docker image"
    exit 1
fi

# Upload Docker image to VM
echo "Uploading Docker image to VM (this may take a few minutes)..."
gcloud compute scp --compress "$TAR_FILE" $INSTANCE:/tmp/ --project $PROJECT --zone $ZONE 2>&1 | grep -v "^Updating project ssh metadata\.\.\." | grep -v "^Updating instance ssh metadata\.\.\." | grep -v "^\.$" | grep -v "^done\.$" || true

# Clean up local tar file
rm -f "$TAR_FILE"

# Build docker run command
DOCKER_RUN_CMD="docker run -d \
    --name $CONTAINER_NAME \
    --restart unless-stopped \
    -p 127.0.0.1:18080:8000 \
    -e PORT=8000 \
    -e PYTHONUNBUFFERED=1"

DOCKER_RUN_CMD="$DOCKER_RUN_CMD $IMAGE_NAME:latest"

# Load image and run container on VM
echo "Loading Docker image and starting container on VM..."
run_gcloud_ssh "
    # Load the Docker image (use sudo in case user is not in docker group)
    sudo docker load -i /tmp/${IMAGE_NAME}.tar
    rm -f /tmp/${IMAGE_NAME}.tar
    
    # Kill any processes on port 18080 in case they're running outside Docker
    sudo lsof -ti:18080 | xargs sudo kill -9 2>/dev/null || true
    
    # Stop and remove existing container if it exists
    sudo docker stop $CONTAINER_NAME 2>/dev/null || true
    sudo docker rm $CONTAINER_NAME 2>/dev/null || true
    
    # Run the new container
    # Bind to 127.0.0.1 so nginx can reach it (not exposed publicly)
    sudo $DOCKER_RUN_CMD
    
    # Verify container is running
    sudo docker ps | grep $CONTAINER_NAME
" "Deploying Docker container" || exit 1

echo ""
echo "Docker deployment completed successfully!"
echo ""
echo "Container status:"
run_gcloud_ssh "sudo docker ps | grep $CONTAINER_NAME" "Checking container status" || true
echo ""
echo "Container logs (last 20 lines):"
run_gcloud_ssh "sudo docker logs --tail 20 $CONTAINER_NAME" "Viewing container logs" || true
echo ""
echo "The app should be available at: https://hackernews.photogroup.network"
echo ""
echo "To view logs: gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command 'sudo docker logs -f $CONTAINER_NAME'"
echo "To restart: gcloud compute ssh $INSTANCE --project $PROJECT --zone $ZONE --command 'sudo docker restart $CONTAINER_NAME'"

