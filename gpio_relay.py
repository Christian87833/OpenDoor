import asyncio
import logging
import os

logger = logging.getLogger(__name__)

RELAY_PIN = int(os.getenv("RELAY_PIN", "17"))
RELAY_ACTIVE_LOW = os.getenv("RELAY_ACTIVE_LOW", "true").lower() == "true"
BUZZ_DURATION = float(os.getenv("BUZZ_DURATION", "3.0"))

# GPIO state — initialised lazily via init()
_chip = None
_gpio_available = False

# Pin levels
_ON  = 0 if RELAY_ACTIVE_LOW else 1   # active-low: ON = LOW
_OFF = 1 if RELAY_ACTIVE_LOW else 0


def init():
    """Call this after logging is configured (e.g. from FastAPI lifespan)."""
    global _chip, _gpio_available
    try:
        import lgpio
        _chip = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(_chip, RELAY_PIN, _OFF)   # start in OFF state
        _gpio_available = True
        logger.info("GPIO initialized — relay on BCM %d (active_%s)",
                    RELAY_PIN, "low" if RELAY_ACTIVE_LOW else "high")
    except Exception as e:
        _gpio_available = False
        logger.warning("GPIO not available — running in mock mode (%s)", e)


async def buzz_door(duration: float = BUZZ_DURATION) -> bool:
    """Pulse the relay for `duration` seconds. Returns False if already active."""
    if buzz_door._active:
        return False
    buzz_door._active = True

    try:
        if _gpio_available:
            lgpio.gpio_write(_chip, RELAY_PIN, _ON)
            logger.info("Relay ON  (BCM %d)", RELAY_PIN)
            await asyncio.sleep(duration)
            lgpio.gpio_write(_chip, RELAY_PIN, _OFF)
            logger.info("Relay OFF (BCM %d)", RELAY_PIN)
        else:
            logger.info("[MOCK] Relay ON  for %.1fs", duration)
            await asyncio.sleep(duration)
            logger.info("[MOCK] Relay OFF")
    except Exception as e:
        logger.error("Relay error: %s", e)
    finally:
        buzz_door._active = False

    return True

buzz_door._active = False


def cleanup():
    global _chip
    if _gpio_available and _chip is not None:
        try:
            lgpio.gpio_write(_chip, RELAY_PIN, _OFF)   # ensure relay is off
            lgpio.gpiochip_close(_chip)
            _chip = None
            logger.info("GPIO cleaned up")
        except Exception as e:
            logger.warning("GPIO cleanup error: %s", e)
