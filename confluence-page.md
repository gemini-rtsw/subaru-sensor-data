# Subaru Sensors EPICS System

## Overview

The Subaru Sensors system fetches environmental data from the Subaru telescope JSON API and republishes it as EPICS PVs. It also provides a live web dashboard. The system runs as two Docker containers on the GWS VM **mkogwsioc-lv2**.

## Architecture

```
Subaru JSON API (naoj.org)
        |
        v
  +-----------+        +-----------+
  |  IOC      |        |  Web      |
  |  Server   | <-PVA- |  Server   | --> Browser (port 8000)
  |           |        |           |
  | CA: 15064 |        | HTTP:8000 |
  | PVA:15075 |        |           |
  +-----------+        +-----------+
     Python/pcaspy/p4p    Python/FastAPI

  Both containers use host networking on mkogwsioc-lv2
```

**Data flow:** The IOC fetches sensor data from `https://www.naoj.org/Weather/data/SubaruSensors.json` every 1 second and updates 46 EPICS PVs via both Channel Access and PVAccess. The web server reads PVs via PVAccess and pushes updates to browser clients over WebSocket.

## Host VM

| | |
|---|---|
| **VM** | mkogwsioc-lv2 |
| **Network mode** | Host (both containers) |
| **Auto-restart** | Yes (`restart: unless-stopped`) |
| **Docker enabled at boot** | Must be enabled: `sudo systemctl enable docker` |

Non-standard EPICS ports are used to avoid conflicts with the existing GWS IOC on the same host.

## Ports

| Service | Port | Protocol |
|---|---|---|
| CA search/server | 15064 | UDP + TCP |
| PVA server | 15075 | TCP |
| PVA broadcast | 15076 | UDP |
| Web dashboard | 8000 | HTTP |

The native GWS IOC continues to use the standard EPICS ports (5064/5065).

## EPICS PVs

All PVs use the `subaru:` prefix. Updated every 1 second.

| Group | PVs | Unit |
|---|---|---|
| Humidity | `subaru:humidity:{ne,nw,se,sw,obs,ctrl,outside}` | % RH |
| Temperature | `subaru:temp:{ne,nw,se,sw,obs,ctrl,outside}`, `subaru:dewpoint` | Deg C |
| Wind | `subaru:wind:{opt,ir,rear}` | m/s |
| Pressure | `subaru:pressure` | mbar |
| Particles (ET) | `subaru:particles:et:{0.3-0.5,0.5-1.0,1.0-2.5,2.5-4.0,4.0-10.0,total}` | count/mL |
| Particles (OF) | `subaru:particles:of:{0.3-0.5,0.5-1.0,1.0-2.5,2.5-4.0,4.0-10.0,total}` | count/mL |
| SO2 | `subaru:so2:{et,of,noaa}` | ppm |
| Timestamps | `subaru:timestamp`, `subaru:timestamp:{et,of}:{particles,so2}`, `subaru:timestamp:noaa:so2` | epoch sec |

## Client Access

### Channel Access (caget/camonitor)

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST=mkogwsioc-lv2
export EPICS_CA_SERVER_PORT=15064

caget subaru:humidity:ne
camonitor subaru:temp:outside
```

### PVAccess (pvget)

```bash
export EPICS_PVA_AUTO_ADDR_LIST=NO
export EPICS_PVA_ADDR_LIST=mkogwsioc-lv2
export EPICS_PVA_BROADCAST_PORT=15076
export EPICS_PVA_SERVER_PORT=15075

pvget subaru:humidity:ne
```

### Web Dashboard

```
http://mkogwsioc-lv2:8000
```

The dashboard includes an expandable "EPICS Connection Info" section with copy-ready client setup commands.

## Operations

### Service management

```bash
ssh mkogwsioc-lv2
cd ~/subaru-sensors

./subaru-sensors.sh              # Pull latest images and start
./subaru-sensors.sh stop         # Stop services
./subaru-sensors.sh status       # Container status and recent logs
./subaru-sensors.sh logs         # Tail live logs
```

### Manual docker commands

```bash
docker compose up -d             # Start (no image pull)
docker compose down              # Stop
docker compose logs ioc --tail=50
docker compose logs web --tail=50
```

### After VM reboot

Containers restart automatically via Docker's `restart: unless-stopped` policy. No manual intervention needed as long as Docker is enabled at boot.

## Source Code

GitLab: `nsf-noirlab/gemini/rtsw/iocs/subaru-sensor-data`

Docker images are built by CI/CD and pulled from the GitLab container registry.
