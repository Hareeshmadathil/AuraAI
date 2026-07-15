"""Regression tests for deterministic private narration WAV assembly."""

from __future__ import annotations

import json
import socket
import struct
import subprocess
import wave
from pathlib import Path
from uuid import uuid4

import pytest

from core import ValidationError
from private_video_production.models import (
    NarrationSegment,
    VoiceProfile,
    VoiceSynthesisRequest,
)
from private_video_production.voice import VoiceSynthesisService, WindowsSapiAdapter
from private_video_production.voice.wav import (
    PcmWaveNormalizer,
    TARGET_CHANNELS,
    TARGET_SAMPLE_RATE,
    TARGET_SAMPLE_WIDTH,
    inspect_wav,
)


VOICE = VoiceProfile(name="Local Test Voice", culture="en-US", gender="Neutral")


class FormatVoiceAdapter:
    """Create local test WAVs with an explicit format per invocation."""

    def __init__(self, formats: list[tuple[int, int, int, int]]) -> None:
        self.formats = formats
        self.texts: list[str] = []

    def list_voices(self):
        return [VOICE]

    def synthesize_chunk(self, *, text, voice, output_path):
        index = len(self.texts)
        self.texts.append(text)
        sample_rate, channels, sample_width, frame_count = self.formats[index]
        if sample_width == 1:
            sample = bytes([128 + index])
        elif sample_width == 2:
            sample = struct.pack("<h", 1000 if index == 0 else -1000)
        else:
            sample = bytes(sample_width)
        with wave.open(str(output_path), "wb") as audio:
            audio.setnchannels(channels)
            audio.setsampwidth(sample_width)
            audio.setframerate(sample_rate)
            audio.writeframes(sample * channels * frame_count)


class FailingNormalizer:
    def normalize(self, source, target, *, chunk_index):
        raise ValidationError(
            "Test normalization failure.",
            error_code="NARRATION_NORMALIZATION_FAILED",
        )


def _request(*, pauses: tuple[int, ...] = (500, 0)) -> VoiceSynthesisRequest:
    segments = [
        NarrationSegment(
            segment_id=f"segment-{index}",
            sequence=index,
            heading=f"Segment {index}",
            text=f"Narration segment {index}",
            expected_duration_seconds=1,
            pause_after_ms=pause,
        )
        for index, pause in enumerate(pauses, start=1)
    ]
    return VoiceSynthesisRequest(
        mission_id=uuid4(),
        voice=VOICE,
        segments=segments,
        output_relative_path=Path("voice/narration.wav"),
    )


def _metadata(root: Path):
    return inspect_wav(root / "voice/narration.wav", chunk_index=0)


def test_identical_formats_with_different_frame_counts_join_in_order(tmp_path: Path) -> None:
    adapter = FormatVoiceAdapter([(24_000, 1, 2, 2_400), (24_000, 1, 2, 4_800)])
    result = VoiceSynthesisService(adapter, tmp_path).synthesize(_request())

    metadata = _metadata(tmp_path)
    assert result.success is True
    assert metadata.frame_count == 7_200
    with wave.open(str(tmp_path / "voice/narration.wav"), "rb") as audio:
        frames = audio.readframes(audio.getnframes())
    assert struct.unpack("<h", frames[:2])[0] == 1000
    assert struct.unpack("<h", frames[4_800:4_802])[0] == -1000


@pytest.mark.parametrize(
    "formats",
    [
        [(16_000, 1, 2, 1_600), (22_050, 1, 2, 2_205)],
        [(24_000, 1, 2, 2_400), (24_000, 2, 2, 2_400)],
        [(24_000, 1, 1, 2_400), (24_000, 1, 4, 2_400)],
    ],
    ids=["sample-rates", "mono-stereo", "sample-widths"],
)
def test_real_format_differences_are_normalized(tmp_path: Path, formats) -> None:
    result = VoiceSynthesisService(FormatVoiceAdapter(formats), tmp_path).synthesize(
        _request()
    )

    metadata = _metadata(tmp_path)
    assert result.success is True
    assert metadata.sample_rate == TARGET_SAMPLE_RATE
    assert metadata.channels == TARGET_CHANNELS
    assert metadata.sample_width == TARGET_SAMPLE_WIDTH
    assert metadata.encoding == "pcm_s16le"


def test_normalized_duration_matches_sum_and_wav_is_valid(tmp_path: Path) -> None:
    formats = [(16_000, 1, 2, 1_600), (22_050, 2, 1, 4_410)]
    VoiceSynthesisService(FormatVoiceAdapter(formats), tmp_path).synthesize(_request())

    target = tmp_path / "voice/narration.wav"
    header = target.read_bytes()[:12]
    assert header[:4] == b"RIFF"
    assert header[8:12] == b"WAVE"
    metadata = inspect_wav(target, chunk_index=0)
    assert metadata.duration_seconds == pytest.approx(0.3, abs=0.001)
    assert metadata.frame_count > 0


def test_pause_text_and_chunk_order_are_preserved(tmp_path: Path) -> None:
    adapter = FormatVoiceAdapter([(24_000, 1, 2, 240), (24_000, 1, 2, 240)])
    VoiceSynthesisService(adapter, tmp_path).synthesize(_request(pauses=(500, 0)))

    assert adapter.texts == ["Narration segment 1 ..", "Narration segment 2"]


def test_success_removes_all_temporary_chunks(tmp_path: Path) -> None:
    adapter = FormatVoiceAdapter([(24_000, 1, 2, 240), (24_000, 1, 2, 240)])
    VoiceSynthesisService(adapter, tmp_path).synthesize(_request())

    assert not list(tmp_path.rglob("*.source.wav"))
    assert not list(tmp_path.rglob("*.input.txt"))
    assert not list(tmp_path.rglob("failure-metadata.json"))
    assert not (tmp_path / "voice/.narration-chunks").exists()


def test_normalization_failure_retains_safe_metadata_not_audio(tmp_path: Path) -> None:
    adapter = FormatVoiceAdapter([(22_050, 1, 2, 2_205), (22_050, 1, 2, 2_205)])
    service = VoiceSynthesisService(adapter, tmp_path, normalizer=FailingNormalizer())

    with pytest.raises(ValidationError, match="Test normalization failure"):
        service.synthesize(_request())

    chunk_root = tmp_path / "voice/.narration-chunks"
    summary = json.loads((chunk_root / "failure-metadata.json").read_text(encoding="utf-8"))
    assert summary["safe_error_code"] == "NARRATION_NORMALIZATION_FAILED"
    assert summary["temporary_audio_retained"] is False
    assert summary["chunks"][0]["source"]["sample_rate"] == 22_050
    assert summary["chunks"][0]["normalized"] is None
    assert not list(chunk_root.glob("*.wav"))
    assert not list(chunk_root.glob("*.input.txt"))


def test_synthesis_uses_no_network(tmp_path: Path, monkeypatch) -> None:
    def reject_network(*args, **kwargs):
        raise AssertionError("Narration synthesis must not use the network.")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    adapter = FormatVoiceAdapter([(24_000, 1, 2, 240), (24_000, 1, 2, 240)])
    assert VoiceSynthesisService(adapter, tmp_path).synthesize(_request()).success is True


def test_windows_sapi_sets_explicit_format_and_never_uses_shell(tmp_path: Path) -> None:
    calls = []
    output = tmp_path / "chunk.wav"

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24_000)
            audio.writeframes(b"\x00\x00" * 240)
        return subprocess.CompletedProcess(args, 0, "", "")

    adapter = WindowsSapiAdapter(command_runner=runner)
    adapter.synthesize_chunk(text="Safe local test.", voice=VOICE, output_path=output)

    args, kwargs = calls[0]
    script = args[-1]
    assert kwargs["shell"] is False
    assert "SpeechAudioFormatInfo" in script
    assert "24000" in script
    assert "AudioBitsPerSample]::Sixteen" in script
    assert "AudioChannel]::Mono" in script
    assert "Invoke-WebRequest" not in script
    assert "http" not in script.casefold()
    assert not output.with_suffix(".input.txt").exists()


def test_pcm_normalizer_rejects_invalid_wav(tmp_path: Path) -> None:
    source = tmp_path / "invalid.wav"
    source.write_bytes(b"not-a-wave")

    with pytest.raises(ValidationError, match="valid RIFF/WAVE"):
        PcmWaveNormalizer().normalize(source, tmp_path / "normalized.wav", chunk_index=1)
