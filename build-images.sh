#!/bin/bash

# build-images.sh - Build Subaru Sensors Docker images locally

set -e  # Exit on any error

echo "🏗️  Building Subaru Sensors Docker Images"
echo "==========================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

print_status "Starting build process..."

# Set image names to match docker-compose.yml
IOC_IMAGE="registry.gitlab.com/nsf-noirlab/gemini/rtsw/iocs/subaru-sensor-data/ioc:master"
WEB_IMAGE="registry.gitlab.com/nsf-noirlab/gemini/rtsw/iocs/subaru-sensor-data/web:master"

# Build IOC image
print_status "Building IOC image..."
if docker build -t "$IOC_IMAGE" ./ioc; then
    print_status "✅ IOC image built successfully"
else
    print_error "❌ Failed to build IOC image"
    exit 1
fi

# Build web image  
print_status "Building web image..."
if docker build -t "$WEB_IMAGE" ./web; then
    print_status "✅ Web image built successfully"
else
    print_error "❌ Failed to build web image"
    exit 1
fi

print_status "🎉 All images built successfully!"
print_status ""
print_status "Images built:"
print_status "  $IOC_IMAGE"
print_status "  $WEB_IMAGE"
print_status ""
print_status "You can now run with docker-compose:"
print_status "  docker-compose up -d"
print_status ""
print_status "Or check the built images with:"
print_status "  docker images | grep subaru-sensor" 