"""Transcribe one recording into the Smart Add box. Nothing is saved here."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from organiser.agent.voice import (
    MAX_BODY,
    Transcriber,
    VoiceRefused,
    VoxtralTranscriber,
    take_audio,
    transcribe_with,
)
from organiser.config import get_settings
from organiser.db import get_db
from organiser.services.settings import voice_mic_on

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


def get_transcriber(session: Session = Depends(get_db)) -> Transcriber:
    settings = get_settings()
    if not settings.voice_input_enabled or not voice_mic_on(session):
        raise HTTPException(status_code=404, detail="Not found.")
    key = settings.mistral_api_key.get_secret_value().strip()
    if not key:
        raise HTTPException(status_code=503, detail="Voice is off.")
    return VoxtralTranscriber(
        key,
        settings.mistral_base_url,
        settings.mistral_transcribe_model,
        settings.mistral_timeout_seconds,
    )


@router.post("/transcribe")
async def transcribe(
    request: Request,
    session: Session = Depends(get_db),
    transcriber: Transcriber = Depends(get_transcriber),
) -> dict:
    """Audio in memory, text back. The recording is not written, stored, or logged."""
    if not get_settings().voice_input_enabled or not voice_mic_on(session):
        raise HTTPException(status_code=404, detail="Not found.")
    length = request.headers.get("content-length")
    if length:
        try:
            announced = int(length)
        except ValueError:
            announced = MAX_BODY + 1
        if announced > MAX_BODY:
            raise HTTPException(status_code=413, detail="That recording is too long.")
    body = await request.body()
    try:
        audio, media = take_audio(body, request.headers.get("content-type", ""))
        text = transcribe_with(transcriber, audio, media)
    except VoiceRefused as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    logger.info("voice transcribed bytes=%s", len(audio))
    return {"text": text}
