"""Creator-ready projection over the existing deterministic production package."""
from __future__ import annotations

from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import Field

from core import AuraBaseModel
from production.models import (
    ProductionPackage, Storyboard, SubtitlePackage, ThumbnailPlan,
    VideoAssemblyManifest, VideoScript, VoiceoverPlan,
)


class CreatorMetadata(AuraBaseModel):
    title_options: list[str] = Field(min_length=3, max_length=5)
    description: str
    hashtags: list[str] = Field(min_length=1, max_length=20)
    upload_checklist: list[str] = Field(min_length=1)


class CreatorReadyPackage(AuraBaseModel):
    package_id: UUID
    source_production_package_id: UUID
    final_script: VideoScript
    narration_package: VoiceoverPlan
    scene_breakdown: Storyboard
    editing_instructions: VideoAssemblyManifest
    subtitle_package: SubtitlePackage
    thumbnail_brief: ThumbnailPlan
    metadata: CreatorMetadata
    deterministic: Literal[True] = True
    rendering_performed: Literal[False] = False
    upload_performed: Literal[False] = False
    publishing_performed: Literal[False] = False


class CreatorPackageService:
    def build(self, source: ProductionPackage) -> CreatorReadyPackage:
        title = source.script.title
        topic = source.input.topic
        hashtags = [f"#{word.strip('.,').title().replace(' ', '')}" for word in topic.split() if len(word) > 3][:8]
        return CreatorReadyPackage(
            package_id=uuid5(NAMESPACE_URL, f"creator-package:{source.package_id}"),
            source_production_package_id=source.package_id,
            final_script=source.script,
            narration_package=source.voiceover_plan,
            scene_breakdown=source.storyboard,
            editing_instructions=source.assembly_manifest,
            subtitle_package=source.subtitle_package,
            thumbnail_brief=source.thumbnail_plan,
            metadata=CreatorMetadata(
                title_options=[title, f"{title}: A Practical Guide", f"How to Apply {topic}"],
                description=f"A practical, evidence-aware guide to {topic}. Review sources and apply the workflow safely.",
                hashtags=hashtags or ["#AuraAI"],
                upload_checklist=[
                    "Founder reviews final script and evidence.",
                    "Creative Quality result is approved.",
                    "Platform metadata is validated.",
                    "Separate publishing approval remains required.",
                ],
            ),
        )
