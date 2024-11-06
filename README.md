# snapcast-mpris-proxy

Proxy Snapcast client and stream status to the MPRIS D-Bus interface.

Primarily intended to integrate with [mpris-monitor](https://github.com/mill1000/mpris-monitor).

## Usage
Use the included Makefile to intall via pipx and setup a systemd service.

### Configure
Use `systemctl edit snapcast-mpris-proxy.service` to change environment variables `SNAPCAST_SERVER` and `SNAPCAST_CLIENT` as needed.