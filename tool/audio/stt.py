"""
Captura de áudio pelo microfone e transcrição com faster-whisper.
"""

import io
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wav
from faster_whisper import WhisperModel

from config import (
    AUDIO_CHANNELS,
    AUDIO_MAX_SECONDS,
    AUDIO_SAMPLE_RATE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
)

_model: WhisperModel | None = None


def get_whisper_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )
    return _model


def record_audio(duration: int = AUDIO_MAX_SECONDS) -> np.ndarray:
    """Grava áudio do microfone por até `duration` segundos e retorna array numpy."""
    audio = sd.rec(
        int(duration * AUDIO_SAMPLE_RATE),
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="float32",
    )
    sd.wait()
    return audio.flatten()


def record_until_silence(
    silence_threshold: float = 0.01,
    silence_duration: float = 1.5,
    max_duration: int = AUDIO_MAX_SECONDS,
) -> np.ndarray:
    """
    Grava até detectar silêncio por `silence_duration` segundos
    ou até `max_duration` segundos.
    """
    chunk_size = int(AUDIO_SAMPLE_RATE * 0.1)  # janelas de 100ms
    max_chunks = int(max_duration * AUDIO_SAMPLE_RATE / chunk_size)
    silence_chunks = int(silence_duration * AUDIO_SAMPLE_RATE / chunk_size)

    recorded: list[np.ndarray] = []
    silent_count = 0
    speaking_started = False

    with sd.InputStream(
        samplerate=AUDIO_SAMPLE_RATE,
        channels=AUDIO_CHANNELS,
        dtype="float32",
    ) as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(chunk_size)
            chunk = chunk.flatten()
            recorded.append(chunk)

            rms = float(np.sqrt(np.mean(chunk**2)))

            if rms > silence_threshold:
                speaking_started = True
                silent_count = 0
            elif speaking_started:
                silent_count += 1
                if silent_count >= silence_chunks:
                    break

    return np.concatenate(recorded) if recorded else np.zeros(1)


def transcribe(audio: np.ndarray) -> str:
    """Transcreve um array numpy de áudio (float32, 16kHz) para texto."""
    model = get_whisper_model()

    # faster-whisper aceita arquivo WAV em memória
    buf = io.BytesIO()
    wav.write(buf, AUDIO_SAMPLE_RATE, (audio * 32767).astype(np.int16))
    buf.seek(0)

    segments, _ = model.transcribe(
        buf,
        language=WHISPER_LANGUAGE,
        beam_size=1,           # beam_size=1 reduz latência no Pi 5
        vad_filter=True,       # filtra trechos sem voz
    )

    return " ".join(seg.text.strip() for seg in segments).strip()


def record_and_transcribe() -> str:
    """Grava até silêncio e retorna a transcrição."""
    audio = record_until_silence()
    return transcribe(audio)
