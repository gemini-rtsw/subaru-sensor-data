#!/bin/bash

# Script to deploy containers from GitLab registry if available, or build locally

# Set default registry if not provided
export CI_REGISTRY_IMAGE=${CI_REGISTRY_IMAGE:-subaru-sensors}
export CI_COMMIT_REF_SLUG=${CI_COMMIT_REF_SLUG:-latest}

# Try to login to GitLab registry if credentials are available
if [ -n "$CI_REGISTRY_USER" ] && [ -n "$CI_REGISTRY_PASSWORD" ] && [ -n "$CI_REGISTRY" ]; then
  echo "Logging in to GitLab registry..."
  docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  REGISTRY_LOGIN=$?
else
  REGISTRY_LOGIN=1
  echo "GitLab registry credentials not available, will build locally"
fi

# Pull or build containers
if [ $REGISTRY_LOGIN -eq 0 ]; then
  echo "Attempting to pull images from GitLab registry..."
  docker compose pull || PULL_FAILED=1
  
  if [ -n "$PULL_FAILED" ]; then
    echo "Failed to pull some images, falling back to local build"
    docker compose build
  fi
else
  echo "Building containers locally..."
  docker compose build
fi

# Start the containers
docker compose up -d

echo "Deployment complete!" 