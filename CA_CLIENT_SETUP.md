# Channel Access Client Setup

This IOC uses alternate CA ports (15064/15065) to avoid conflicts with the native EPICS 7 IOC on the same host.

## For CA Clients to Connect to This IOC

Set these environment variables on your CA client systems:

```bash
export EPICS_CA_SERVER_PORT=15065
export EPICS_CA_REPEATER_PORT=15064
export EPICS_CA_ADDR_LIST="<your-vm-ip>:15064"
export EPICS_CA_AUTO_ADDR_LIST=NO
```

Replace `<your-vm-ip>` with the IP address of your Rocky 8 VM.

## Example Usage

```bash
# Set environment for this IOC
export EPICS_CA_SERVER_PORT=15065
export EPICS_CA_REPEATER_PORT=15064
export EPICS_CA_ADDR_LIST="192.168.1.100:15064"  # Replace with your VM IP
export EPICS_CA_AUTO_ADDR_LIST=NO

# Test connection
caget subaru:pressure
camonitor subaru:temp:outside
```

## For Native EPICS 7 IOC Clients

Keep the standard environment (or unset the above variables):

```bash
unset EPICS_CA_SERVER_PORT
unset EPICS_CA_REPEATER_PORT
export EPICS_CA_AUTO_ADDR_LIST=YES
# or set EPICS_CA_ADDR_LIST to your network's broadcast address
```

## Port Summary

| Service | Standard Ports | This IOC Ports | Purpose |
|---------|---------------|----------------|---------|
| CA Search/Beacon | 5064 UDP | 15064 UDP | Client searches, server beacons |
| CA Connections | 5065+ TCP | 15065+ TCP | Data connections |
| PVA Server | 5075 TCP | 5075 TCP | PVA data (unchanged) |
| PVA Broadcast | 5076 UDP | 5076 UDP | PVA search (unchanged) |

The native EPICS 7 IOC continues to use the standard ports (5064/5065), while this dockerized IOC uses the alternate ports (15064/15065).

