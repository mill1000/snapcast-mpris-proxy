#!/usr/bin/env python3

import argparse
import asyncio
import logging
from enum import StrEnum
from typing import NoReturn

import snapcast.control
from dbus_fast import BusType, PropertyAccess
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_property

_LOGGER = logging.getLogger("snapcast-mpris-proxy")


class PlaybackStatus(StrEnum):
    PLAYING = "Playing"
    PAUSED = "Paused"
    STOPPED = "Stopped"


class MediaPlayer2Interface(ServiceInterface):
    """MPRIS MediaPlayer2 Interface"""

    def __init__(self) -> None:
        super().__init__("org.mpris.MediaPlayer2")

    # Indicate we can't be controlled in any way
    @dbus_property(name="CanQuit", access=PropertyAccess.READ)
    def can_quit(self) -> "b":
        return False

    @dbus_property(name="CanSetFullscreen", access=PropertyAccess.READ)
    def can_set_fullscreen(self) -> "b":
        return False

    @dbus_property(name="CanRaise", access=PropertyAccess.READ)
    def can_raise(self) -> "b":
        return False

    @dbus_property(name="HasTrackList", access=PropertyAccess.READ)
    def has_track_list(self) -> "b":
        return False

    @dbus_property(name="Identity", access=PropertyAccess.READ)
    def identity(self) -> "s":
        return "Snapcast MPRIS Proxy"


class MediaPlayer2PlayerInterface(ServiceInterface):

    """MPRIS MediaPlayer2 Player Interface"""

    def __init__(self) -> None:
        super().__init__("org.mpris.MediaPlayer2.Player")

        self._playback_status = PlaybackStatus.STOPPED

    # Supported properties
    @dbus_property(name="PlaybackStatus", access=PropertyAccess.READ)
    def playback_status(self) -> "s":
        return self._playback_status

    @playback_status.setter
    def playback_status(self, status: PlaybackStatus) -> None:
        if self._playback_status == status:
            return

        _LOGGER.info("Set PlaybackStatus to %s.", status)
        self._playback_status = status
        self.emit_properties_changed(
            {"PlaybackStatus": self._playback_status})

    # Indicate we can't be controlled in any way

    @dbus_property(name="CanControl", access=PropertyAccess.READ)
    def can_control(self) -> "b":
        return False

    @dbus_property(name="CanGoNext", access=PropertyAccess.READ)
    def can_go_next(self) -> "b":
        return False

    @dbus_property(name="CanGoPrevious", access=PropertyAccess.READ)
    def can_go_previous(self) -> "b":
        return False

    @dbus_property(name="CanPlay", access=PropertyAccess.READ)
    def can_play(self) -> "b":
        return False

    @dbus_property(name="CanPause", access=PropertyAccess.READ)
    def can_pause(self) -> "b":
        return False

    @dbus_property(name="CanSeek", access=PropertyAccess.READ)
    def can_seek(self) -> "b":
        return False


async def _reconnect(server) -> None:
    """Attempt to reconnect to the Snapcast server."""
    server.stop()

    while True:
        try:
            await server.start()
            break
        except OSError as e:
            _LOGGER.error(
                "Failed to connect to Snapcast server '%s'.", server)
            await asyncio.sleep(2)

    _LOGGER.info("Reconnected to Snapcast server '%s'.", server)


async def run(args) -> NoReturn:
    """Main proxy function/."""

    # Connect to the Snapcast server
    loop = asyncio.get_running_loop()
    try:
        server = await snapcast.control.create_server(loop, args.hostname)
    except OSError as e:
        _LOGGER.error(
            "Failed to connect to Snapcast server '%s'.", args.hostname)
        exit(1)

    _LOGGER.info("Connected to Snapcast server '%s'.", server)

    # Try to find the Snapcast client
    client = next(
        (c for c in server.clients if c.friendly_name == args.client), None)

    if client is None:
        _LOGGER.error(
            "Failed to find Snapcast client '%s' on the server.", args.client)
        exit(1)

    if client.connected == False:
        _LOGGER.warning("Client is not connected to server.")

    # Connect to the system bus
    _LOGGER.info("Connecting to system bus.")
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

    # Construct and export MPRIS interfaces
    _LOGGER.info("Exporting MediaPlayer2 interface.")
    mediaplayer2 = MediaPlayer2Interface()
    bus.export("/org/mpris/MediaPlayer2", mediaplayer2)

    _LOGGER.info("Exporting MediaPlayer2.Player interface.")
    player = MediaPlayer2PlayerInterface()
    bus.export("/org/mpris/MediaPlayer2", player)

    # Acquire our friendly name
    name = f"org.mpris.MediaPlayer2.snapcast_mpris_proxy.client_{args.client}"
    _LOGGER.info(f"Requesting friendly name '{name}' on bus.")
    await bus.request_name(name)

    while True:
        # Get latest data
        status, error = await server.status()

        if not isinstance(status, dict):
            _LOGGER.warning(
                "Error fetching status from server. Error: %s", error)
            await _reconnect(server)
            continue

        # Update server object
        server.synchronize(status)

        # Check client and stream state
        stream_idle = client.group.stream_status == "idle" if client.group is not None else True
        client_idle = client.muted or stream_idle

        _LOGGER.debug("Client idle: %s. Client mute: %s. Stream idle: %s.",
                      client_idle, client.muted, stream_idle)

        # Set playback status
        if not client_idle:
            player.playback_status = PlaybackStatus.PLAYING

        elif stream_idle:
            player.playback_status = PlaybackStatus.STOPPED

        elif client.muted:
            # Treat muted client as paused
            player.playback_status = PlaybackStatus.PAUSED

        await asyncio.sleep(.5)


def main() -> None:
    # Basic log config
    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)

    # Argument parsing
    parser = argparse.ArgumentParser(
        description="Proxy Snapcast client and stream status to MPRIS D-Bus interface.")
    parser.add_argument(
        "--verbose", help="Enable debug messages.", action="store_true")
    parser.add_argument(
        "hostname", help="Snapcast server hostname.")
    parser.add_argument("client", help="Snapcast client name.")

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
