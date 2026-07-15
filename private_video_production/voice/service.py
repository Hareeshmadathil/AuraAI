"""Deterministic narration normalization, auditioning, and chunk assembly."""

from __future__ import annotations

import hashlib
import json
import re
import wave
from pathlib import Path

from core import ValidationError, get_logger

from private_video_production.models import (
    NarrationSegment,
    VoiceProfile,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
)
from private_video_production.voice.contracts import LocalVoiceAdapter
from private_video_production.voice.models import PRONUNCIATION_OVERRIDES
from private_video_production.voice.wav import (
    PcmWaveNormalizer,
    WavMetadata,
    WaveNormalizer,
    format_signature,
    inspect_wav,
)


LOGGER = get_logger(__name__)


class VoiceSynthesisService:
    """Compose injected local voice adapters with bounded memory use."""

    def __init__(
        self,
        adapter: LocalVoiceAdapter,
        output_root: Path,
        *,
        normalizer: WaveNormalizer | None = None,
    ) -> None:
        self._adapter = adapter
        self._root = output_root.resolve()
        self._normalizer = normalizer or PcmWaveNormalizer()

    def list_voices(self) -> list[VoiceProfile]:
        return self._adapter.list_voices()

    def create_audition(
        self,
        *,
        mission_id,
        voice: VoiceProfile,
        opening_text: str,
    ) -> VoiceSynthesisResult:
        """Create approximately 20–30 seconds from the revised opening."""

        words = opening_text.split()[:65]
        segment = NarrationSegment(
            segment_id="audition-opening",
            sequence=1,
            heading="Opening audition",
            text=" ".join(words),
            expected_duration_seconds=26,
            pause_after_ms=0,
        )
        request = VoiceSynthesisRequest(
            mission_id=mission_id,
            voice=voice,
            segments=[segment],
            output_relative_path=Path("voice/voice-audition.wav"),
            audition=True,
            pronunciation_overrides=PRONUNCIATION_OVERRIDES,
        )
        return self.synthesize(request)

    def synthesize(self, request: VoiceSynthesisRequest) -> VoiceSynthesisResult:
        """Synthesize segment chunks and combine compatible PCM WAV files."""

        available = {voice.name: voice for voice in self.list_voices()}
        if request.voice.name not in available:
            return VoiceSynthesisResult(
                request_id=request.request_id,
                success=False,
                available=False,
                voice_name=request.voice.name,
                message="Selected local voice is unavailable; no audio was created.",
            )
        target = (self._root / request.output_relative_path).resolve()
        self._require_within_root(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        chunk_root = target.parent / f".{target.stem}-chunks"
        chunk_root.mkdir(parents=True, exist_ok=True)
        failure_summary = chunk_root / "failure-metadata.json"
        failure_summary.unlink(missing_ok=True)
        chunks: list[Path] = []
        diagnostics: list[dict[str, object]] = []
        failed = False
        try:
            for index, segment in enumerate(request.segments, start=1):
                source_chunk = chunk_root / f"chunk-{index:03d}.source.wav"
                chunk = chunk_root / f"chunk-{index:03d}.wav"
                text = self._normalize(
                    segment.text,
                    request.pronunciation_overrides,
                    segment.pause_after_ms,
                )
                self._adapter.synthesize_chunk(
                    text=text,
                    voice=request.voice,
                    output_path=source_chunk,
                )
                source_metadata = inspect_wav(source_chunk, chunk_index=index)
                diagnostic = {
                    "source": source_metadata.model_dump(mode="json"),
                    "normalized": None,
                }
                diagnostics.append(diagnostic)
                normalized_metadata = self._normalizer.normalize(
                    source_chunk,
                    chunk,
                    chunk_index=index,
                )
                diagnostic["normalized"] = normalized_metadata.model_dump(mode="json")
                self._log_metadata(normalized_metadata)
                source_chunk.unlink(missing_ok=True)
                chunks.append(chunk)
            duration, sample_rate, channels = self._combine(chunks, target)
        except Exception as error:
            failed = True
            target.unlink(missing_ok=True)
            self._write_failure_summary(failure_summary, diagnostics, error)
            raise
        finally:
            for temporary in chunk_root.glob("*.wav"):
                temporary.unlink(missing_ok=True)
            for temporary in chunk_root.glob("*.input.txt"):
                temporary.unlink(missing_ok=True)
            if not failed and chunk_root.exists() and not any(chunk_root.iterdir()):
                chunk_root.rmdir()
        return VoiceSynthesisResult(
            request_id=request.request_id,
            success=True,
            available=True,
            voice_name=request.voice.name,
            output_relative_path=request.output_relative_path,
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            content_hash=hashlib.sha256(target.read_bytes()).hexdigest(),
            chunks_created=len(chunks),
            message="Local synthetic narration created for private review.",
        )

    @staticmethod
    def _normalize(text: str, overrides: dict[str, str], pause_ms: int) -> str:
        value = re.sub(r"\s+", " ", text).strip()
        for term, pronunciation in sorted(
            overrides.items(), key=lambda item: len(item[0]), reverse=True
        ):
            value = value.replace(term, pronunciation)
        pause_words = " " + "." * max(1, pause_ms // 250) if pause_ms else ""
        return value + pause_words

    @staticmethod
    def _combine(chunks: list[Path], target: Path) -> tuple[float, int, int]:
        if not chunks:
            raise ValidationError("At least one narration chunk is required.")
        metadata = [inspect_wav(chunk, chunk_index=index) for index, chunk in enumerate(chunks, 1)]
        expected_format = format_signature(metadata[0])
        if any(format_signature(item) != expected_format for item in metadata[1:]):
            raise ValidationError(
                "Narration chunks use incompatible WAV formats.",
                error_code="INCOMPATIBLE_NARRATION_WAV",
            )
        frames: list[bytes] = []
        for chunk in chunks:
            with wave.open(str(chunk), "rb") as source:
                frames.append(source.readframes(source.getnframes()))
        with wave.open(str(target), "wb") as output:
            output.setnchannels(metadata[0].channels)
            output.setsampwidth(metadata[0].sample_width)
            output.setframerate(metadata[0].sample_rate)
            output.setcomptype("NONE", "not compressed")
            for frame_data in frames:
                output.writeframes(frame_data)
        with wave.open(str(target), "rb") as result:
            duration = result.getnframes() / result.getframerate()
            return duration, result.getframerate(), result.getnchannels()

    @staticmethod
    def _log_metadata(metadata: WavMetadata) -> None:
        LOGGER.info(
            "Narration chunk metadata: index=%d sample_rate=%d channels=%d "
            "sample_width=%d frame_count=%d duration_seconds=%.6f encoding=%s",
            metadata.chunk_index,
            metadata.sample_rate,
            metadata.channels,
            metadata.sample_width,
            metadata.frame_count,
            metadata.duration_seconds,
            metadata.encoding,
        )

    @staticmethod
    def _write_failure_summary(
        path: Path,
        diagnostics: list[dict[str, object]],
        error: Exception,
    ) -> None:
        error_code = getattr(error, "error_code", "NARRATION_SYNTHESIS_FAILED")
        payload = {
            "safe_error_code": error_code,
            "chunks": diagnostics,
            "temporary_audio_retained": False,
        }
        try:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError:
            LOGGER.warning("Narration failure metadata could not be persisted.")

    def _require_within_root(self, path: Path) -> None:
        try:
            path.relative_to(self._root)
        except ValueError as error:
            raise ValidationError("Voice output escapes the configured root.") from error
