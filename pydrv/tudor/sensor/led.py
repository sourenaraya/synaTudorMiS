from __future__ import annotations

import enum
import logging
import struct
import time
import tudor

# VCSFW_CMD_LED_EX2, as used by synaWudfBioUsb123.dll (Kensington 047d:8054 and
# Synaptics 06cb:00d6). See rev/notes/led-ex2-default-profiles.md and the
# 2026-10-16 entry in rev/FINDINGS.md.

# (vid, pid) of the sensors whose Windows driver drives an LED
LED_EX2_DEVICES = {(0x047D, 0x8054), (0x06CB, 0x00D6), (0x06CB, 0x00F9)}

STATUS_SENSOR_BAD_CMD = 0x401


class LedEvent(enum.IntEnum):
    IDLE = 0
    WAITING_FOR_FINGER = 1
    ENROLL_ACCEPTED = 2
    ENROLL_REJECTED = 3
    MATCH_SUCCESS = 4
    MATCH_FAILURE = 5


IDLE_ACTION = (0x0000, 0x20000000, 0x00000000, 0x00000000)
ZERO_ACTION = (0x0000, 0x00000000, 0x00000000, 0x00000000)

# Built-in LED_EX2 default profiles. (duration in ms, six actions of
# (field0, param0, param1, param2)). The 0x39 frame layout is fixed; only the
# action values differ, and they are a property of the SENSOR (vid:pid) - not
# of the driver build, vendor, or laptop platform. "Series" below is
# Synaptics' UMDF driver build number = the 4th DriverVer component
# (6.0.X.NNNN) with the leading "1" dropped (6.0.2.1154 -> 154); it is NOT a
# monotonic generation (series 154 predates 136). A series ships a per-sensor
# table, so one series can cover several sensors, and one sensor keeps the same
# table across the series that ship it (00f9's table is identical in 136 and
# 154). See rev/notes/led-ex2-default-profiles.md, the 2026-10-16 FINDINGS
# entry, and the closed upstream PR #7.
#
# Profile A: series 123 (synaWudfBioUsb123.dll, 6.0.20.1123) @ 0x1800cc8a0.
# Used by 047d:8054 (Kensington) and 06cb:00d6 (Synaptics). The 8054 table is
# byte-identical in upstream PR #7, which also gates its LED handling by
# (vid, pid) - i.e. per-sensor, confirming the keying below.
LED_PROFILES_A = {
    LedEvent.IDLE: (0, (IDLE_ACTION,) * 6),
    LedEvent.WAITING_FOR_FINGER: (
        160000,
        (
            (0xFFFF, 0x20000505, 0x00000000, 0x00000505),
            (0xFFFF, 0x20000505, 0x00000000, 0x00000505),
            (0xFFFF, 0x20000505, 0x00000000, 0x00000505),
            ZERO_ACTION,
            ZERO_ACTION,
            ZERO_ACTION,
        ),
    ),
    LedEvent.ENROLL_ACCEPTED: (
        500,
        (
            (0x01F4, 0x20000507, 0x00000000, 0x00000505),
            IDLE_ACTION,
            (0x01F4, 0x20000500, 0x00000000, 0x00000000),
            IDLE_ACTION,
            ZERO_ACTION,
            ZERO_ACTION,
        ),
    ),
    LedEvent.ENROLL_REJECTED: (
        1000,
        (
            (0x01F4, 0x20000107, 0x00000101, 0x00000000),
            IDLE_ACTION,
            (0x01F4, 0x20000100, 0x00000000, 0x00000000),
            IDLE_ACTION,
            ZERO_ACTION,
            ZERO_ACTION,
        ),
    ),
    LedEvent.MATCH_SUCCESS: (
        500,
        (
            (0x01F4, 0x20000507, 0x00000000, 0x00000505),
            IDLE_ACTION,
            (0x01F4, 0x20000500, 0x00000000, 0x00000000),
            IDLE_ACTION,
            ZERO_ACTION,
            ZERO_ACTION,
        ),
    ),
    LedEvent.MATCH_FAILURE: (
        1000,
        (
            (0x004B, 0x20000107, 0x00000101, 0x00000000),
            (0x004B, 0x20000001, 0x00000000, 0x00000000),
            (0x004B, 0x20000101, 0x00000000, 0x00000000),
            (0x004B, 0x20000001, 0x00000000, 0x00000000),
            ZERO_ACTION,
            ZERO_ACTION,
        ),
    ),
}

# Profile B: series 154 (synaWudfBioUsb154.dll, 6.0.2.1154, T14 Gen 3 AMD) @
# 0x1800e90c0; byte-identical in series 136 (synaWudfBioUsb136.dll,
# 6.0.42.1136, T14 Gen 3 Intel) @ file 0xf6050. Used by 06cb:00f9 (fw 10.1).
# Live-verified (green solid + orange blink).
LED_PROFILES_B = {
    LedEvent.IDLE: (
        0,
        (
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
    LedEvent.WAITING_FOR_FINGER: (
        0,
        (
            (0xFFFF, 0x20009607, 0x00009696, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
    LedEvent.ENROLL_ACCEPTED: (
        500,
        (
            (0x01F4, 0x20000007, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
    LedEvent.ENROLL_REJECTED: (
        1000,
        (
            (0x00A6, 0x20003C01, 0x00000000, 0x00003C3C),
            (0x00A6, 0x20000001, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
    LedEvent.MATCH_SUCCESS: (
        500,
        (
            (0x01F4, 0x20000007, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
    LedEvent.MATCH_FAILURE: (
        1000,
        (
            (0x00A6, 0x20003C01, 0x00000000, 0x00003C3C),
            (0x00A6, 0x20000001, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
            (0x0000, 0x20000000, 0x00000000, 0x00000000),
        ),
    ),
}

# Which profile each sensor (vid:pid) needs. Unlisted sensors default to A.
LED_PROFILES_BY_DEVICE = {
    (0x047D, 0x8054): LED_PROFILES_A,
    (0x06CB, 0x00D6): LED_PROFILES_A,
    (0x06CB, 0x00F9): LED_PROFILES_B,
}

# Default profile for unlisted sensors.
LED_PROFILES = LED_PROFILES_A


def led_ex2_command(event: LedEvent, profiles: dict = None) -> bytes:
    """Build the 0x7d-byte LED_EX2 command for one of the built-in events.

    Each 20-byte action is a u16, two zero bytes and four u32. The last u32
    is always zero, and the two before it only carry 16 bits, which is all
    sendLedEx2Cmd copies.
    """
    duration, actions = (profiles or LED_PROFILES)[event]
    cmd = struct.pack("<BI", tudor.Command.LED_EX2, duration)
    for field0, p0, p1, p2 in actions:
        assert p1 <= 0xFFFF and p2 <= 0xFFFF
        cmd += struct.pack("<HxxIIII", field0, p0, p1, p2, 0)
    assert len(cmd) == 0x7D
    return cmd


class SensorLed:
    """Sends the LED events the way the Windows Tudor driver does.

    Uses a per-sensor profile (see LED_PROFILES_BY_DEVICE, keyed by vid:pid);
    the 0x39 frame layout is fixed, only the action values differ per sensor.

    - An LED failure is logged and never fails the operation.
    - A timed result indication is never cut short: waiting for finger is sent
      once it has run out, any other event requested meanwhile is dropped.
    """

    def __init__(
        self,
        comm: tudor.CommunicationInterface,
        enabled: bool,
        profiles: dict = None,
    ):
        self.comm = comm
        self.enabled = enabled
        self.profiles = profiles or LED_PROFILES
        self.last_event = LedEvent.IDLE
        self.last_time = 0.0

    def set_event(self, event: LedEvent):
        if not self.enabled:
            return

        if self.last_event != LedEvent.WAITING_FOR_FINGER:
            remaining = (
                self.profiles[self.last_event][0] / 1000
                - (time.monotonic() - self.last_time)
            )
            if remaining > 0:
                if event != LedEvent.WAITING_FOR_FINGER:
                    logging.debug(
                        "LED event %s dropped, %s still showing"
                        % (event.name, self.last_event.name)
                    )
                    return
                time.sleep(remaining)

        self.last_event = event
        self.last_time = time.monotonic()
        self.send(event)

    def send(self, event: LedEvent):
        """Send one event right away, without the timing rules."""
        cmd = led_ex2_command(event, self.profiles)
        for attempt in range(2):
            resp = self.comm.send_command(cmd, 2, check_response=False)
            (status,) = struct.unpack("<H", resp[:2])
            # the command is sent once more if the sensor rejects it
            if status == STATUS_SENSOR_BAD_CMD and attempt == 0:
                continue
            break

        if status not in tudor.SUCCESS_STATUS:
            logging.warning(
                "LED_EX2 (%s) failed with status 0x%04x" % (event.name, status)
            )
