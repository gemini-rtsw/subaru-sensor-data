#!/bin/bash
#
# Subaru Sensors - Service Management Script
#
# USAGE:
#   ./subaru-sensors.sh          Pull latest images and start services
#   ./subaru-sensors.sh stop     Stop all services
#   ./subaru-sensors.sh status   Show service status and logs
#   ./subaru-sensors.sh logs     Tail live logs
#
# AFTER VM REBOOT:
#   Containers restart automatically (restart: unless-stopped).
#   Docker must be enabled at boot:  sudo systemctl enable docker
#
# EPICS CLIENT ACCESS:
#   The IOC uses non-standard ports to avoid conflicts with the host EPICS 7 IOC.
#
#   For caget/camonitor on this host:
#     export EPICS_CA_AUTO_ADDR_LIST=NO
#     export EPICS_CA_ADDR_LIST=localhost
#     export EPICS_CA_SERVER_PORT=15064
#
#   For pvget on this host:
#     export EPICS_PVA_AUTO_ADDR_LIST=NO
#     export EPICS_PVA_ADDR_LIST=localhost
#     export EPICS_PVA_BROADCAST_PORT=15076
#     export EPICS_PVA_SERVER_PORT=15075
#
#   Web dashboard: http://localhost:8000
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$(basename "$0")"
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

show_info() {
    echo ""
    info "Services started."
    info ""
    info "  Web dashboard:  http://localhost:8000"
    info ""
    info "  CA access (caget/camonitor):"
    info "    export EPICS_CA_AUTO_ADDR_LIST=NO"
    info "    export EPICS_CA_ADDR_LIST=localhost"
    info "    export EPICS_CA_SERVER_PORT=15064"
    info ""
    info "  PVA access (pvget):"
    info "    export EPICS_PVA_AUTO_ADDR_LIST=NO"
    info "    export EPICS_PVA_ADDR_LIST=localhost"
    info "    export EPICS_PVA_BROADCAST_PORT=15076"
    info "    export EPICS_PVA_SERVER_PORT=15075"
    info ""
    info "  Logs:    ./$SCRIPT_NAME logs"
    info "  Status:  ./$SCRIPT_NAME status"
    info "  Stop:    ./$SCRIPT_NAME stop"
}

# --- Commands ---

case "${1:-start}" in
    start)
        info "Pulling latest images..."
        if ! docker-compose -f "$COMPOSE_FILE" pull 2>/dev/null; then
            warn "Could not pull images (registry unreachable?). Starting with cached images."
        fi

        info "Starting Subaru Sensors services..."
        docker-compose -f "$COMPOSE_FILE" up -d
        show_info
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
