"""Strict PCM WAV inspection and deterministic local normalization."""

from __future__ import annotations

import audioop
import wave
from pathlib import Path
from typing import Protocol

from core import AuraBaseModel, ValidationError


TARGET_SAMPLE_RATE = 24_000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2


class WavMetadata(AuraBaseModel):
    """Safe, content-free metadata for one narration chunk."""

    chunk_index: int
    sample_rate: int
    channels: int
    sample_width: int
    frame_count: int
    duration_seconds: float
    encoding: str


class WaveNormalizer(Protocol):
    """Provider-neutral contract for local WAV normalization."""

    def normalize(self, source: Path, target: Path, *, chunk_index: int) -> WavMetadata: ...


class PcmWaveNormalizer:
    """Normalize uncompressed PCM WAV audio with Python's local standard library."""

    def __init__(
        self,
        *,
        sample_rate: int = TARGET_SAMPLE_RATE,
        channels: int = TARGET_CHANNELS,
        sample_width: int = TARGET_SAMPLE_WIDTH,
    ) -> None:
        if sample_rate <= 0 or channels != 1 or sample_width != 2:
            raise ValueError("Narration target must be mono 16-bit PCM at a positive rate.")
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width = sample_width

    def normalize(
        self,
        source: Path,
        target: Path,
        *,
        chunk_index: int,
    ) -> WavMetadata:
        """Convert one PCM WAV to the configured deterministic target format."""

        try:
            with wave.open(str(source), "rb") as audio:
                channels = audio.getnchannels()
                sample_width = audio.getsampwidth()
                sample_rate = audio.getframerate()
                source_frame_count = audio.getnframes()
                compression = audio.getcomptype()
                frames = audio.readframes(source_frame_count)
        except (OSError, EOFError, wave.Error) as error:
            raise ValidationError(
                "Narration chunk is not a valid RIFF/WAVE file.",
                error_code="INVALID_NARRATION_WAV",
            ) from error

        if compression != "NONE":
            raise ValidationError(
                "Narration normalization requires uncompressed PCM WAV input.",
                error_code="UNSUPPORTED_NARRATION_ENCODING",
            )
        if channels not in (1, 2) or sample_width not in (1, 2, 3, 4):
            raise ValidationError(
                "Narration chunk uses an unsupported PCM layout.",
                error_code="UNSUPPORTED_NARRATION_FORMAT",
            )

        try:
            if channels == 2:
                frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
                channels = 1
            if sample_width == 1:
                frames = audioop.bias(frames, 1, -128)
            if sample_width != self.sample_width:
                frames = audioop.lin2lin(frames, sample_width, self.sample_width)
                sample_width = self.sample_width
            if sample_rate != self.sample_rate:
                expected_frame_count = round(
                    source_frame_count * self.sample_rate / sample_rate
                )
                frames, _ = audioop.ratecv(
                    frames,
                    sample_width,
                    channels,
                    sample_rate,
                    self.sample_rate,
                    None,
                )
                sample_rate = self.sample_rate
                frame_size = sample_width * channels
                actual_frame_count = len(frames) // frame_size
                if actual_frame_count < expected_frame_count:
                    final_frame = frames[-frame_size:] if frames else bytes(frame_size)
                    frames += final_frame * (expected_frame_count - actual_frame_count)
                elif actual_frame_count > expected_frame_count:
                    frames = frames[: expected_frame_count * frame_size]
        except audioop.error as error:
            raise ValidationError(
                "Narration PCM normalization failed.",
                error_code="NARRATION_NORMALIZATION_FAILED",
            ) from error

        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with wave.open(str(target), "wb") as output:
                output.setnchannels(self.channels)
                output.setsampwidth(self.sample_width)
                output.setframerate(self.sample_rate)
                output.setcomptype("NONE", "not compressed")
                output.writeframes(frames)
        except (OSError, wave.Error) as error:
            target.unlink(missing_ok=True)
            raise ValidationError(
                "Normalized narration WAV could not be written.",
                error_code="NARRATION_NORMALIZATION_FAILED",
            ) from error

        metadata = inspect_wav(target, chunk_index=chunk_index)
        if format_signature(metadata) != (
            self.channels,
            self.sample_width,
            self.sample_rate,
            "pcm_s16le",
        ):
            target.unlink(missing_ok=True)
            raise ValidationError(
                "Normalized narration WAV does not match the required format.",
                error_code="NARRATION_NORMALIZATION_FAILED",
            )
        return metadata


def inspect_wav(path: Path, *, chunk_index: int) -> WavMetadata:
    """Read safe WAV metadata without exposing audio or filesystem paths."""

    try:
        with wave.open(str(path), "rb") as audio:
            channels = audio.getnchannels()
            sample_width = audio.getsampwidth()
            sample_rate = audio.getframerate()
            frame_count = audio.getnframes()
            compression = audio.getcomptype()
    except (OSError, EOFError, wave.Error) as error:
        raise ValidationError(
            "Narration chunk is not a valid RIFF/WAVE file.",
            error_code="INVALID_NARRATION_WAV",
        ) from error

    encoding = (
        f"pcm_s{sample_width * 8}le"
        if compression == "NONE" and sample_width > 1
        else "pcm_u8"
        if compression == "NONE" and sample_width == 1
        else f"compressed_{compression.casefold()}"
    )
    return WavMetadata(
        chunk_index=chunk_index,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        frame_count=frame_count,
        duration_seconds=round(frame_count / sample_rate, 6),
        encoding=encoding,
    )


def format_signature(metadata: WavMetadata) -> tuple[int, int, int, str]:
    """Return only properties that define WAV compatibility, excluding duration."""

    return (
        metadata.channels,
        metadata.sample_width,
        metadata.sample_rate,
        metadata.encoding,
    )
