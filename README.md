# snapcast-mpris-proxy

Proxy Snapcast client and stream status to MPRIS D-Bus interface. Primarily intended to be used with [mpris-monitor](https://github.com/mill1000/mpris-monitor) to control external equipment.

## Systemd
Use `systemctl edit snapcast-mpris-proxy.service` to change environment variables `SNAPCAST_SERVER` and `SNAPCAST_CLIENT` as needed.