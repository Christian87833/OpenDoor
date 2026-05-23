import asyncio
import logging
import os

logger = logging.getLogger(__name__)

RELAY_PIN = int(os.getenv("RELAY_PIN", "17"))
RELAY_ACTIVE_LOW = os.getenv("RELAY_ACTIVE_LOW", "true").lower() == "true"
BUZZ_DURATION = float(os.getenv("BUZZ_DURATION", "3.0"))

try:
    from gpiozero import OutputDevice
    # active_high=False → pin LOW = relay ON (typisch für 4-Kanal-Boards)
    relay = OutputDevice(RELAY_PIN, active_high=not RELAY_ACTIVE_LOW, initial_value=False)
    _gpio_available = True
    logger.info("GPIO initialized — relay on pin BCM %d (active_%s)",
                RELAY_PIN, "low" if RELAY_ACTIVE_LOW else "high")
except Exception as e:
    _gpio_available = False
    logger.warning("GPIO not available — running in mock mode (%s)", e)

_buzzing = False


async def buzz_door(duration: float = BUZZ_DURATION) -> bool:
    """Pulse the relay for `duration` seconds. Returns False if already buzzing."""
    global _buzzing
    if _buzzing:
        return False

    _buzzing = True
    try:
        if _gpio_available:
            relay.on()
            logger.info("Relay ON  (pin BCM %d)", RELAY_PIN)
            await asyncio.sleep(duration)
            relay.off()
            logger.info("Relay OFF (pin BCM %d)", RELAY_PIN)
        else:
            logger.info("[MOCK] Relay ON  for %.1fs", duration)
            await asyncio.sleep(duration)
            logger.info("[MOCK] Relay OFF")
    finally:
        _buzzing = False

    return True


def cleanup():
    if _gpio_available:
        relay.close()
        logger.info("GPIO cleaned up")
