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

# Check if docker-compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    print_error "docker-compose is not available. Please install docker-compose."
    exit 1
fi

print_status "Starting build process..."

# Build IOC image
print_status "Building IOC image..."
if docker-compose build ioc; then
    print_status "✅ IOC image built successfully"
else
    print_error "❌ Failed to build IOC image"
    exit 1
fi

# Build web image
print_status "Building web image..."
if docker-compose build web; then
    print_status "✅ Web image built successfully"
else
    print_error "❌ Failed to build web image"
    exit 1
fi

print_status "🎉 All images built successfully!"
print_status ""
print_status "You can now run the system with:"
print_status "  docker-compose up -d"
print_status ""
print_status "Or check the built images with:"
print_status "  docker images | grep subaru-sensor" 