#!/usr/bin/env python3

import argparse
import asyncio
import logging
from enum import IntEnum
from typing import NoReturn

import kasa
import snapcast.control

_LOGGER = logging.getLogger("snapcast-monitor")


class AsyncTimer():
    """A timer class built on asyncio."""

    def __init__(self, timeout: float, callback) -> None:
        self._timeout = timeout
        self._callback = callback

    async def _run(self) -> None:
        await asyncio.sleep(self._timeout)
        await self._callback()

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    def cancel(self) -> None:
        self._task.cancel()


class State(IntEnum):
    IDLE = 0
    IDLE_COUNTDOWN = 1
    MUTE = 2
    ACTIVE = 3


class SystemController():
    """Class to manage system state."""

    def __init__(self, device) -> None:
        self._device = device
        self._state = State.IDLE
        self._timer = None

    async def _turn_on(self) -> None:
        _LOGGER.info("Enabling system power.")

        # Preamp = 0
        # Amp 1 = 1
        # Amp 2 = 2
        for plug in self._device.children:
            await plug.turn_on()
            await asyncio.sleep(1)

        self._state = State.ACTIVE

    async def _turn_off(self) -> None:
        _LOGGER.info("Disabling system power.")

        # Turn off in reverse order
        for plug in reversed(self._device.children):
            await plug.turn_off()
            await asyncio.sleep(1)

        self._state = State.IDLE

        # Stop and destroy timer if present
        if self._timer:
            self._timer.cancel()
            self._timer = None

    async def update(self, client) -> None:
        stream_idle = client.group.stream_status == "idle"
        client_idle = client.muted or stream_idle

        # _LOGGER.info("Steam idle %s, client mute %s, client idle %s", stream_idle, client.muted, client_idle)
        # _LOGGER.info("state %s ", self._state)
        if not client_idle:
            # Power on if coming out of idle
            if self._state == State.IDLE:
                await self._turn_on()

            # Ensure state is active
            self._state = State.ACTIVE

            # Disable the shutdown timer if running
            if self._timer:
                _LOGGER.debug("Disabled shutdown timer.")
                self._timer.cancel()
                self._timer = None

        elif stream_idle:
            # Nothing to do if already idle
            if self._state == State.IDLE or self._state == State.IDLE_COUNTDOWN:
                return

            if self._state == State.MUTE and self._timer is not None:
                _LOGGER.debug("Disabled shutdown timer.")
                self._timer.cancel()
                self._timer = None

            self._state = State.IDLE_COUNTDOWN

            # Start shutdown timer with short interval
            _LOGGER.debug("Starting short ({0} s) shutdown timer.".format(10))
            self._timer = AsyncTimer(10, self._turn_off)
            self._timer.start()

        elif client.muted:
            # TODO Treat muted client as "paused"?

            # Nothing to do if already muted or idle
            if self._state == State.MUTE or self._state == State.IDLE:
                return

            # Disable the shutdown timer if running
            if self._timer:
                _LOGGER.debug("Disabled shutdown timer.")
                self._timer.cancel()
                self._timer = None

            self._state = State.MUTE

            # Start shutdown timer with long interval
            _LOGGER.debug("Starting long ({0} s) shutdown timer.".format(60))
            self._timer = AsyncTimer(60, self._turn_off)
            self._timer.start()


async def _discover():
    """Discover Kasa devices on the network."""

   # Discover available devices
    _LOGGER.info("Discovering Kasa devices.")
    devices = await kasa.Discover.discover(timeout=1)
    _LOGGER.info("Found {0} devices.".format(len(devices)))

    return devices


async def run(args) -> NoReturn:
    """Main monitor function."""

    if args.kasa_device is None:
        _LOGGER.error("Kasa device must be supplied.")
        exit(1)

    if args.hostname is None:
        _LOGGER.error("Snapcast server hostname must be supplied.")
        exit(1)

    if args.hostname is None:
        _LOGGER.error("Snapcast client name must be supplied.")
        exit(1)

    devices = await _discover()

    # Find first device with matching alias
    device = next((d for _, d in devices.items()
                  if d.alias == args.kasa_device), None)

    if device is None:
        _LOGGER.error("Could not find Kasa device '%s'.", args.kasa_device)
        exit()

    # Update device information
    await device.update()

    # Connect to the Snapcast server
    loop = asyncio.get_running_loop()
    try:
        server = await snapcast.control.create_server(loop, args.hostname)
    except OSError as e:
        _LOGGER.error(
            "Failed to connect to Snapcast server '%s'.", args.hostname)
        exit(1)

    # Try to find the Snapcast client
    client = next(
        (c for c in server.clients if c.friendly_name == args.client), None)

    if client is None:
        _LOGGER.error(
            "Failed to find Snapcast client '%s' on the server.", args.client)
        exit(1)

    if client.connected == False:
        _LOGGER.warning("Client is not connected to server.")

    controller = SystemController(device)

    while True:
        await asyncio.sleep(.5)
        # Update Snapcast state
        server.synchronize(await server.status())

        # Update controller
        await controller.update(client)


async def discover(args) -> NoReturn:
    """Discover and print available Kasa devices."""

    # Discover available devices
    devices = await _discover()

    if len(devices):
        _LOGGER.info("Discovered devices:")
        for _, device in devices.items():
            _LOGGER.info(device)

    exit()


def main():
    # Basic log config
    logging.basicConfig(
        format='%(levelname)s: %(message)s', level=logging.INFO)
    _LOGGER = logging.getLogger("mpris-monitor")

    # Argument parsing
    parser = argparse.ArgumentParser(description="Automate system power by monitoring the Snapcast server.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "--discover", help="Discover Kasa devices on the network.", action="store_true")
    # parser.add_argument("--pause_timeout", help="Disable system power when paused for this duration (seconds).", default=60, type=int)
    # parser.add_argument("--stop_timeout", help="Disable system power when stopped for this duration (seconds).", default=5, type=int)
    parser.add_argument(
        "--verbose", help="Enable debug messages.", action="store_true")
    parser.add_argument(
        "kasa_device", help="Kasa device to control.", nargs="?")
    parser.add_argument(
        "hostname", help="Snapcast server hostname.", nargs="?")
    parser.add_argument("client", help="Snapcast client name.", nargs="?")

    args = parser.parse_args()

    if args.verbose:
        _LOGGER.setLevel(logging.DEBUG)

    func = discover if args.discover else run
    try:
        asyncio.run(func(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
