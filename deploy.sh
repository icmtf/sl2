#!/bin/bash
echo "Running deploy.sh..."

# Load environment variables from .env file.
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

# Get current git branch name (strip any non-alphanumeric characters)
GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD | sed 's/[^a-zA-Z0-9]//g')

# Set up NETWORK_NAME variable using git branch name
NETWORK_NAME="${APP_NAME:-CodeHorizon}_${GIT_BRANCH}_network"

echo "Current Git Branch: $GIT_BRANCH"
echo "Docker Network used in Compose file: '${NETWORK_NAME}'"

# Ensure network exists
if ! docker network ls | grep -q "$NETWORK_NAME"; then
    echo "Creating new Docker Network '$NETWORK_NAME'..."
    docker network create "$NETWORK_NAME"
    sleep 2
    echo "Docker Network '$NETWORK_NAME' has been created."
else
    echo "Docker Network '$NETWORK_NAME' already exists."
fi

# Create a temporary env file
echo "Creating temporary .env file with current git branch..."
(
    # Read all lines except APP_ENV_NAME
    grep -v "^APP_ENV_NAME=" .env
    # Add new APP_ENV_NAME
    echo "APP_ENV_NAME=$GIT_BRANCH"
) > .env.tmp

# Check if arguments were passed to the script.
if [ $# -eq 0 ]; then
    echo "Running: docker compose --env-file .env.tmp up --build"
    docker compose --env-file .env.tmp up --build
else
    echo "Running: docker compose --env-file .env.tmp $@"
    docker compose --env-file .env.tmp $@
fi

# Clean up
echo "Cleaning up temporary files..."
rm .env.tmp
