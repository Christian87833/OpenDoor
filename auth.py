import base64
import json
import logging
import os

import webauthn
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

import database

logger = logging.getLogger(__name__)

RP_ID = os.environ["RP_ID"]
RP_ORIGIN = os.environ["RP_ORIGIN"]
RP_NAME = os.getenv("RP_NAME", "OpenDoor")

# Single-owner app: one fixed user identity
_USER_ID = b"opendoor_owner"
_USER_NAME = "owner"


def _b64url_to_bytes(s: str) -> bytes:
    """Decode a base64url string to bytes, handling missing padding."""
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


async def begin_registration() -> tuple[dict, bytes]:
    options = webauthn.generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=_USER_ID,
        user_name=_USER_NAME,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
            resident_key=ResidentKeyRequirement.PREFERRED,
        ),
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )
    return json.loads(webauthn.options_to_json(options)), options.challenge


async def complete_registration(credential: dict, expected_challenge: bytes, device_name: str) -> None:
    verification = webauthn.verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=RP_ID,
        expected_origin=RP_ORIGIN,
        require_user_verification=True,
    )
    await database.save_credential(
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        name=device_name,
    )
    logger.info("Registered new device: %s", device_name)


async def begin_authentication() -> tuple[dict, bytes]:
    credentials = await database.get_all_credentials()
    if not credentials:
        raise ValueError("Keine registrierten Geräte vorhanden")

    options = webauthn.generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=cred["credential_id"])
            for cred in credentials
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(webauthn.options_to_json(options)), options.challenge


async def complete_authentication(credential: dict, expected_challenge: bytes) -> None:
    raw_id = _b64url_to_bytes(credential["rawId"])

    cred = await database.get_credential_by_id(raw_id)
    if not cred:
        raise ValueError("Unbekanntes Gerät")

    verification = webauthn.verify_authentication_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_rp_id=RP_ID,
        expected_origin=RP_ORIGIN,
        credential_public_key=cred["public_key"],
        credential_current_sign_count=cred["sign_count"],
        require_user_verification=True,
    )
    await database.update_sign_count(raw_id, verification.new_sign_count)
    logger.info("Authentication successful for credential %s", credential["id"][:16])
