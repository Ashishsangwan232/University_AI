"""Free text to speech for read-aloud and voice mode (no API key, no cost).

Main voice: Microsoft Edge's neural voice (default Madhur, hi-IN), through the
edge-tts package. It reads Hindi, Hinglish and English naturally but needs
internet. Backup: Piper, open-source voices that run offline - Hindi
(Pratham) for Devanagari text, English (Ryan) otherwise. Piper voices live in
data/voices/ (python scripts/download_voices.py) and are CC BY-NC-SA 4.0:
free for non-commercial use such as this student project.

Text arrives already rewritten for speaking (dates, money, numbers in words)
by the frontend.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
import threading
import wave
from collections import OrderedDict
from pathlib import Path
from typing import Any

from app.core.config import settings

log = logging.getLogger("campusai.agent")

BACKEND_DIR = Path(__file__).resolve().parents[1]
_voices: dict[str, Any] = {}
_lock = threading.Lock()  # one synthesis at a time; Piper is fast enough
_cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
_CACHE_SIZE = 80


def _voice_path(name: str) -> Path:
    folder = Path(settings.tts_voice_dir)
    folder = folder if folder.is_absolute() else BACKEND_DIR / folder
    return folder / f"{name}.onnx"


def voice_for(text: str) -> str:
    """Hindi voice for Devanagari text, English voice for everything else."""
    return settings.tts_voice_hindi if re.search(r"[ऀ-ॿ]", text) else settings.tts_voice_english


def _installed(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def _use_edge() -> bool:
    return settings.tts_engine == "edge" and _installed("edge_tts")


def status() -> dict[str, Any]:
    installed = _installed("piper")
    voices = {name: _voice_path(name).exists() for name in (settings.tts_voice_hindi, settings.tts_voice_english)}
    piper_ok = installed and all(voices.values())
    edge = _use_edge()
    return {
        "available": edge or piper_ok,
        "engine": "edge" if edge else "piper",
        "edge_voice": settings.tts_edge_voice if edge else None,
        "backup": "piper" if piper_ok else None,
        "installed": installed,
        "voices": voices,
    }


def _load(name: str):
    if name not in _voices:
        from piper import PiperVoice  # imported lazily: the app runs without it

        path = _voice_path(name)
        if not path.exists():
            raise RuntimeError(f"Voice {name} is not downloaded. Run: python scripts/download_voices.py")
        _voices[name] = PiperVoice.load(str(path))
        log.info("[tts] loaded voice %s", name)
    return _voices[name]


def preload() -> None:
    """Load both voices in the background at startup, so the first answer read
    aloud does not wait ~3 seconds for the model to load."""
    def run() -> None:
        if _use_edge():
            # The first Edge call is slow (connection set-up): make it now, not
            # when the student is waiting. Piper (the backup) loads on first use.
            try:
                synthesize("नमस्ते")
            except Exception as exc:  # noqa: BLE001
                log.info("[tts] Edge warm-up failed: %s", exc)
            return
        if not status()["available"]:
            return
        for name in (settings.tts_voice_english, settings.tts_voice_hindi):
            try:
                with _lock:
                    _load(name)
            except Exception as exc:  # noqa: BLE001 - read-aloud falls back to browser voices
                log.info("[tts] could not preload %s: %s", name, exc)

    threading.Thread(target=run, name="campusai-tts-preload", daemon=True).start()


def _remember(key: str, value: tuple[bytes, str]) -> tuple[bytes, str]:
    _cache[key] = value
    while len(_cache) > _CACHE_SIZE:
        _cache.popitem(last=False)
    return value


def _edge(text: str) -> bytes:
    """MP3 from the Edge neural voice. Raises when offline or refused."""
    import edge_tts

    async def run() -> bytes:
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, settings.tts_edge_voice).stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                audio.extend(chunk["data"])
        return bytes(audio)

    audio = asyncio.run(asyncio.wait_for(run(), settings.tts_edge_timeout_seconds))
    if not audio:
        raise RuntimeError("the Edge voice returned no audio")
    return audio


def synthesize(text: str) -> tuple[bytes, str]:
    """Audio for the text and its media type. Edge voice first, Piper as the
    offline backup. Raises RuntimeError when neither can speak."""
    text = re.sub(r"\s+", " ", text or "").strip()[: settings.tts_max_chars]
    if not text:
        raise RuntimeError("Nothing to say.")
    if _use_edge():
        key = hashlib.sha1(f"edge|{settings.tts_edge_voice}|{text}".encode("utf-8")).hexdigest()
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
        try:
            return _remember(key, (_edge(text), "audio/mpeg"))
        except Exception as exc:  # noqa: BLE001 - offline or blocked: fall back to Piper
            log.info("[tts] Edge voice failed, using Piper: %s", exc)
    name = voice_for(text)
    key = hashlib.sha1(f"{name}|{text}".encode("utf-8")).hexdigest()
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    try:
        with _lock:
            voice = _load(name)
            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wav:
                voice.synthesize_wav(text, wav)
    except ImportError as exc:
        raise RuntimeError("Piper is not installed. Run: pip install piper-tts") from exc
    return _remember(key, (buffer.getvalue(), "audio/wav"))
