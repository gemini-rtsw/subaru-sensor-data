#!/bin/bash
#
# Subaru Sensors - Production Startup Script
#
# USAGE:
#   ./start.sh          Pull latest images and start services
#   ./start.sh stop     Stop all services
#   ./start.sh status   Show service status and logs
#   ./start.sh logs     Tail live logs
#
# AFTER VM REBOOT:
#   Containers restart automatically (restart: unless-stopped).
#   Docker must be enabled at boot:  sudo systemctl enable docker
#
# EPICS CLIENT ACCESS:
#   The IOC's CA server is on host port 15064 (not the default 5064)
#   to avoid conflicts with the host EPICS 7 IOC.
#
#   For caget/camonitor on this host:
#     export EPICS_CA_ADDR_LIST="localhost:15064 localhost"
#     export EPICS_CA_AUTO_ADDR_LIST=NO
#
#   For PVA (pvget):
#     export EPICS_PVA_ADDR_LIST="localhost:15076 localhost"
#     export EPICS_PVA_AUTO_ADDR_LIST=NO
#
#   Web dashboard: http://localhost:8000
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# --- Preflight checks ---

if ! docker info > /dev/null 2>&1; then
    error "Docker is not running."
    echo "  Start it:   sudo systemctl start docker"
    echo "  Enable it:  sudo systemctl enable docker"
    exit 1
fi

if ! systemctl is-enabled docker > /dev/null 2>&1; then
    warn "Docker is NOT enabled at boot. Containers won't restart after a VM reboot."
    echo "  Fix this:   sudo systemctl enable docker"
    echo ""
fi

# --- Commands ---

case "${1:-start}" in
    start)
        info "Pulling latest images..."
        docker-compose -f "$COMPOSE_FILE" pull

        info "Starting Subaru Sensors services..."
        docker-compose -f "$COMPOSE_FILE" up -d

        echo ""
        info "Services started."
        info ""
        info "  Web dashboard:  http://localhost:8000"
        info ""
        info "  CA access (caget/camonitor):"
        info "    export EPICS_CA_ADDR_LIST=\"localhost:15064 localhost\""
        info "    export EPICS_CA_AUTO_ADDR_LIST=NO"
        info ""
        info "  PVA access (pvget):"
        info "    export EPICS_PVA_ADDR_LIST=\"localhost:15076 localhost\""
        info "    export EPICS_PVA_AUTO_ADDR_LIST=NO"
        info ""
        info "  Logs:    ./start.sh logs"
        info "  Status:  ./start.sh status"
        info "  Stop:    ./start.sh stop"
        ;;

    stop)
        info "Stopping Subaru Sensors services..."
        docker-compose -f "$COMPOSE_FILE" down
        info "Stopped."
        ;;

    status)
        info "Container status:"
        docker-compose -f "$COMPOSE_FILE" ps
        echo ""
        info "Recent logs (last 20 lines per service):"
        docker-compose -f "$COMPOSE_FILE" logs --tail=20
        ;;

    logs)
        docker-compose -f "$COMPOSE_FILE" logs -f --tail=50
        ;;

    *)
        echo "Usage: $0 {start|stop|status|logs}"
        exit 1
        ;;
esac
