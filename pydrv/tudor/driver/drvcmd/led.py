import time

from .cmd import *
from .context import *
from tudor.sensor import LedEvent


@cmd("led")
class CmdLed(Command):
    """Send an LED_EX2 event, or cycle all. Usage: led [event|all]

    The sensor must be initialized first (pair + init). 'event' is a number
    0-5 or a name (IDLE, WAITING_FOR_FINGER, ENROLL_ACCEPTED,
    ENROLL_REJECTED, MATCH_SUCCESS, MATCH_FAILURE). 'all' sends every event in
    turn. Uses the per-sensor profile (see LED_PROFILES_BY_DEVICE).
    """

    def run(self, ctx: CmdContext, args: list):
        led = ctx.sensor.led
        if not led.enabled:
            print("LEDs are not enabled for this sensor (not in LED_EX2_DEVICES).")
            return
        if not ctx.sensor.initialized:
            print(
                "Sensor not initialized - run 'pair' (or load a pairfile) and "
                "'init' first."
            )
            return

        events = list(LedEvent)
        if not args:
            print(
                "LED events: " + ", ".join("%d=%s" % (e, e.name) for e in events)
            )
            print("Usage: led <event|all>")
            return

        target = args[0].strip()
        if target.lower() == "all":
            for e in events:
                print("LED: %s" % e.name)
                led.send(e)
                time.sleep(max(led.profiles[e][0] / 1000.0, 1.5))
            return

        e = None
        if target.isdigit():
            idx = int(target)
            if 0 <= idx < len(events):
                e = events[idx]
        else:
            try:
                e = LedEvent[target.upper()]
            except KeyError:
                e = None

        if e is None:
            print(
                "Unknown event '%s' - use a number 0-%d or a name."
                % (target, len(events) - 1)
            )
            return

        print("LED: %s" % e.name)
        led.send(e)
