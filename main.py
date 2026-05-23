import asyncio
import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import auth
import database
import gpio_relay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    logger.info("OpenDoor started — RP_ID=%s  origin=%s", os.environ["RP_ID"], os.environ["RP_ORIGIN"])
    yield
    gpio_relay.cleanup()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"],
    session_cookie="od_session",
    max_age=3600,
    https_only=True,
    same_site="strict",
)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


# ── Registration ──────────────────────────────────────────────────────────────

@app.get("/api/register/begin")
async def register_begin(request: Request):
    options, challenge = await auth.begin_registration()
    request.session["reg_challenge"] = base64.b64encode(challenge).decode()
    return options


@app.post("/api/register/complete")
async def register_complete(request: Request, body: dict):
    challenge_b64 = request.session.pop("reg_challenge", None)
    if not challenge_b64:
        raise HTTPException(400, "Keine ausstehende Registrierungs-Challenge")

    device_name = body.pop("deviceName", "Mein Gerät")

    try:
        await auth.complete_registration(
            credential=body,
            expected_challenge=base64.b64decode(challenge_b64),
            device_name=device_name,
        )
    except Exception as exc:
        logger.warning("Registration failed: %s", exc)
        raise HTTPException(400, "Registrierung fehlgeschlagen")

    return {"ok": True, "name": device_name}


# ── Authentication + relay ────────────────────────────────────────────────────

@app.get("/api/auth/begin")
async def auth_begin(request: Request):
    try:
        options, challenge = await auth.begin_authentication()
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    request.session["auth_challenge"] = base64.b64encode(challenge).decode()
    return options


@app.post("/api/auth/complete")
async def auth_complete(request: Request, body: dict):
    challenge_b64 = request.session.pop("auth_challenge", None)
    if not challenge_b64:
        raise HTTPException(400, "Keine ausstehende Auth-Challenge")

    try:
        await auth.complete_authentication(
            credential=body,
            expected_challenge=base64.b64decode(challenge_b64),
        )
    except Exception as exc:
        logger.warning("Authentication failed: %s", exc)
        raise HTTPException(401, "Authentifizierung fehlgeschlagen")

    asyncio.create_task(gpio_relay.buzz_door())
    return {"ok": True, "message": "Tür geöffnet!"}


# ── Device management ─────────────────────────────────────────────────────────

@app.get("/api/devices")
async def list_devices():
    creds = await database.get_all_credentials()
    return [{"name": c["name"], "created_at": c["created_at"]} for c in creds]


@app.delete("/api/devices/{index}")
async def delete_device(index: int):
    creds = await database.get_all_credentials()
    if index < 0 or index >= len(creds):
        raise HTTPException(404, "Gerät nicht gefunden")
    await database.delete_credential(creds[index]["credential_id"])
    return {"ok": True}
