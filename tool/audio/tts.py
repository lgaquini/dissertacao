"""
TTS com fallback:
  1. edge-tts (voz feminina PT-BR) — requer internet
  2. Piper (voz masculina PT-BR) — 100% offline
"""

import asyncio
import io
import os
import subprocess
import tempfile
import wave
from pathlib import Path

from config import PIPER_CONFIG, PIPER_MODEL, TTS_VOICE

_piper_voice = None


def _get_piper_voice():
    global _piper_voice
    if _piper_voice is None:
        from piper import PiperVoice
        _piper_voice = PiperVoice.load(str(PIPER_MODEL), config_path=str(PIPER_CONFIG))
    return _piper_voice


def _play(file_path: str) -> None:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
    subprocess.run(["paplay", file_path], env=env, check=True)


def _speak_edge(text: str) -> bool:
    """Tenta sintetizar com edge-tts. Retorna True se funcionou."""
    try:
        import edge_tts
    except ImportError:
        return False

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        communicate = edge_tts.Communicate(text, TTS_VOICE)
        asyncio.run(communicate.save(str(tmp_path)))

        if tmp_path.stat().st_size < 100:
            return False

        _play(str(tmp_path))
        return True
    except Exception:
        return False
    finally:
        tmp_path.unlink(missing_ok=True)


def _speak_piper(text: str) -> None:
    """Sintetiza com Piper (offline)."""
    voice = _get_piper_voice()

    audio_chunks = b""
    sample_rate = 22050
    for chunk in voice.synthesize(text):
        audio_chunks += chunk.audio_int16_bytes
        sample_rate = chunk.sample_rate

    if not audio_chunks:
        return

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_chunks)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(buf.getvalue())

    try:
        _play(str(tmp_path))
    finally:
        tmp_path.unlink(missing_ok=True)


def speak(text: str) -> None:
    """Sintetiza e reproduz. Usa edge-tts (feminina) se possível, senão Piper (offline)."""
    if not text.strip():
        return

    if not _speak_edge(text):
        _speak_piper(text)


def piper_available() -> bool:
    return PIPER_MODEL.exists() and PIPER_CONFIG.exists()
