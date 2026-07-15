"""Deterministic private-video timeline and edit-decision construction."""

from __future__ import annotations

from pathlib import Path

from private_video_production.models import (
    ScenePlan,
    SubtitleCue,
    TimelineClip,
    TimelineMarker,
    TimelineTrack,
    TimelineTransition,
    VoiceSynthesisResult,
)


class PrivateTimelineBuilder:
    """Build inspectible video, narration, and subtitle tracks."""

    def build(
        self,
        scenes: list[ScenePlan],
        subtitles: list[SubtitleCue],
        voice_result: VoiceSynthesisResult | None,
    ) -> tuple[list[TimelineTrack], list[TimelineTransition], list[TimelineMarker]]:
        video_clips = [
            TimelineClip(
                clip_id=scene.scene_id,
                source_relative_path=(
                    Path(f"scenes/{scene.scene_id}.mp4")
                    if not scene.founder_capture_required
                    else None
                ),
                start_seconds=scene.expected_start_seconds,
                end_seconds=scene.expected_end_seconds,
                placeholder=scene.visual.placeholder_watermark is not None,
                metadata={"visual_type": scene.visual.visual_type.value},
            )
            for scene in scenes
        ]
        subtitle_clips = [
            TimelineClip(
                clip_id=cue.cue_id,
                start_seconds=cue.start_seconds,
                end_seconds=cue.end_seconds,
                metadata={"text": cue.text},
            )
            for cue in subtitles
        ]
        tracks = [
            TimelineTrack(track_id="video-main", kind="video", clips=video_clips),
            TimelineTrack(track_id="subtitles", kind="subtitles", clips=subtitle_clips),
        ]
        if voice_result and voice_result.success and voice_result.output_relative_path:
            tracks.append(
                TimelineTrack(
                    track_id="narration",
                    kind="narration",
                    clips=[
                        TimelineClip(
                            clip_id="narration-main",
                            source_relative_path=voice_result.output_relative_path,
                            start_seconds=0,
                            end_seconds=voice_result.duration_seconds or 0.001,
                        )
                    ],
                )
            )
        transitions = [
            TimelineTransition(
                from_clip_id=left.scene_id,
                to_clip_id=right.scene_id,
                kind="short_dissolve",
            )
            for left, right in zip(scenes, scenes[1:])
        ]
        markers: list[TimelineMarker] = []
        for scene in scenes:
            markers.append(
                TimelineMarker(
                    marker_id=f"marker-{scene.scene_id}",
                    at_seconds=scene.expected_start_seconds,
                    kind="placeholder" if scene.founder_capture_required else "scene",
                    label=scene.visual.purpose[:300],
                )
            )
            for evidence in scene.evidence_references:
                markers.append(
                    TimelineMarker(
                        marker_id=f"evidence-{scene.scene_id}-{evidence.reference_id}",
                        at_seconds=scene.expected_start_seconds,
                        kind="evidence",
                        label=evidence.description,
                    )
                )
        duration = max(scene.expected_end_seconds for scene in scenes)
        markers.append(
            TimelineMarker(
                marker_id="founder-review-final",
                at_seconds=duration,
                kind="founder_review",
                label="PRIVATE DRAFT — FOUNDER REVIEW REQUIRED — NOT PUBLISHED",
            )
        )
        return tracks, transitions, markers
