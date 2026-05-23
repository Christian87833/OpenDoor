import asyncio
import logging
import os

logger = logging.getLogger(__name__)

RELAY_PIN = int(os.getenv("RELAY_PIN", "17"))
RELAY_ACTIVE_LOW = os.getenv("RELAY_ACTIVE_LOW", "true").lower() == "true"
BUZZ_DURATION = float(os.getenv("BUZZ_DURATION", "3.0"))

try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(RELAY_PIN, GPIO.OUT)
    # Ensure relay starts in OFF state
    GPIO.output(RELAY_PIN, GPIO.HIGH if RELAY_ACTIVE_LOW else GPIO.LOW)
    _gpio_available = True
    logger.info("GPIO initialized — relay on pin BCM %d", RELAY_PIN)
except (ImportError, RuntimeError):
    _gpio_available = False
    logger.warning("RPi.GPIO not available — running in mock mode (no real relay control)")

_buzzing = False


async def buzz_door(duration: float = BUZZ_DURATION) -> bool:
    """Pulse the relay for `duration` seconds. Returns False if already buzzing."""
    global _buzzing
    if _buzzing:
        return False

    _buzzing = True
    try:
        if _gpio_available:
            on = GPIO.LOW if RELAY_ACTIVE_LOW else GPIO.HIGH
            off = GPIO.HIGH if RELAY_ACTIVE_LOW else GPIO.LOW
            GPIO.output(RELAY_PIN, on)
            logger.info("Relay ON  (pin BCM %d)", RELAY_PIN)
            await asyncio.sleep(duration)
            GPIO.output(RELAY_PIN, off)
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
        GPIO.cleanup()
        logger.info("GPIO cleaned up")
