"""Offline deterministic implementation for every provider capability."""

from __future__ import annotations

from time import perf_counter
from typing import cast

from core import utc_now
from providers.models import (
    AnalyticsAdviceOutput, AnimationOutput, AudienceOutput, FlowOutput,
    HookOutput, ImagePromptOutput, MarketingOutput, MetadataOutput,
    ProviderCapability, ProviderDescriptor, ProviderKind, ProviderOutput,
    ResearchOutput, ReviewOutput, SEOOutput, SceneOutput, ScriptOutput,
    StoryOutput, VideoPromptOutput,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult
from providers.usage import ProviderUsage


class DeterministicProvider:
    """Return stable local models and never call a network or filesystem."""

    descriptor = ProviderDescriptor(
        name="deterministic",
        kind=ProviderKind.DETERMINISTIC,
        capabilities=frozenset(ProviderCapability),
    )

    def generate(
        self,
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderResult[ProviderOutput]:
        started_at = utc_now()
        started = perf_counter()
        output = self._build_output(capability, prompt)
        usage = ProviderUsage(
            provider=self.descriptor.name,
            capability=capability,
            tokens_requested=self._estimate_tokens(prompt.text),
            latency_ms=(perf_counter() - started) * 1000,
            started_at=started_at,
            completed_at=utc_now(),
        )
        return ProviderResult[ProviderOutput](
            request_id=usage.request_id,
            provider=self.descriptor.name,
            output=output,
            usage=usage,
        )

    def research(self, prompt: ProviderPrompt) -> ProviderResult[ResearchOutput]:
        return cast(
            ProviderResult[ResearchOutput],
            self.generate(ProviderCapability.RESEARCH, prompt),
        )

    def generate_script(self, prompt: ProviderPrompt) -> ProviderResult[ScriptOutput]:
        return cast(
            ProviderResult[ScriptOutput],
            self.generate(ProviderCapability.SCRIPT, prompt),
        )

    def generate_hook(self, prompt: ProviderPrompt) -> ProviderResult[HookOutput]:
        return cast(
            ProviderResult[HookOutput],
            self.generate(ProviderCapability.HOOK, prompt),
        )

    def generate_story(self, prompt: ProviderPrompt) -> ProviderResult[StoryOutput]:
        return cast(
            ProviderResult[StoryOutput],
            self.generate(ProviderCapability.STORY, prompt),
        )

    def generate_seo(self, prompt: ProviderPrompt) -> ProviderResult[SEOOutput]:
        return cast(
            ProviderResult[SEOOutput],
            self.generate(ProviderCapability.SEO, prompt),
        )

    def generate_marketing(self, prompt: ProviderPrompt) -> ProviderResult[MarketingOutput]:
        return cast(
            ProviderResult[MarketingOutput],
            self.generate(ProviderCapability.MARKETING, prompt),
        )

    def review(self, prompt: ProviderPrompt) -> ProviderResult[ReviewOutput]:
        return cast(
            ProviderResult[ReviewOutput],
            self.generate(ProviderCapability.REVIEW, prompt),
        )

    def generate_image_prompt(self, prompt: ProviderPrompt) -> ProviderResult[ImagePromptOutput]:
        return cast(
            ProviderResult[ImagePromptOutput],
            self.generate(ProviderCapability.IMAGE_PROMPT, prompt),
        )

    def generate_video_prompt(self, prompt: ProviderPrompt) -> ProviderResult[VideoPromptOutput]:
        return cast(
            ProviderResult[VideoPromptOutput],
            self.generate(ProviderCapability.VIDEO_PROMPT, prompt),
        )

    def generate_metadata(self, prompt: ProviderPrompt) -> ProviderResult[MetadataOutput]:
        return cast(
            ProviderResult[MetadataOutput],
            self.generate(ProviderCapability.METADATA, prompt),
        )

    def analyze_audience(self, prompt: ProviderPrompt) -> ProviderResult[AudienceOutput]:
        return cast(
            ProviderResult[AudienceOutput],
            self.generate(ProviderCapability.AUDIENCE, prompt),
        )

    def advise(self, prompt: ProviderPrompt) -> ProviderResult[AnalyticsAdviceOutput]:
        return cast(
            ProviderResult[AnalyticsAdviceOutput],
            self.generate(ProviderCapability.ANALYTICS, prompt),
        )

    def generate_scenes(self, prompt: ProviderPrompt) -> ProviderResult[SceneOutput]:
        return cast(
            ProviderResult[SceneOutput],
            self.generate(ProviderCapability.SCENE, prompt),
        )

    def generate_animation(self, prompt: ProviderPrompt) -> ProviderResult[AnimationOutput]:
        return cast(
            ProviderResult[AnimationOutput],
            self.generate(ProviderCapability.ANIMATION, prompt),
        )

    def create_flow_plan(self, prompt: ProviderPrompt) -> ProviderResult[FlowOutput]:
        return cast(
            ProviderResult[FlowOutput],
            self.generate(ProviderCapability.FLOW, prompt),
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, (len(text) + 3) // 4)

    @staticmethod
    def _build_output(
        capability: ProviderCapability,
        prompt: ProviderPrompt,
    ) -> ProviderOutput:
        label = prompt.template_name.replace("_", " ")
        outputs: dict[ProviderCapability, ProviderOutput] = {
            ProviderCapability.RESEARCH: ResearchOutput(
                findings=[f"Review evidence for {label}."],
                source_guidance=["Use supplied, attributable sources."],
            ),
            ProviderCapability.SCRIPT: ScriptOutput(
                title=f"Practical guide: {label}",
                sections=["Context", "Evidence", "Action"],
                call_to_action=(
                    "Invite the audience to verify and apply the next step."
                ),
            ),
            ProviderCapability.HOOK: HookOutput(
                primary_hook=f"A clear question about {label}.",
                alternatives=[f"The practical reason {label} matters."],
            ),
            ProviderCapability.STORY: StoryOutput(
                narrative_arc="Problem, evidence, resolution.",
                beats=["Establish need", "Explain evidence", "Offer action"],
            ),
            ProviderCapability.SEO: SEOOutput(
                primary_keyword=label,
                secondary_keywords=[f"{label} guide"],
                title_guidance=(
                    "Use the primary phrase naturally and avoid unsupported claims."
                ),
            ),
            ProviderCapability.MARKETING: MarketingOutput(
                positioning=f"Practical, evidence-aware guidance about {label}.",
                content_pillars=["Education", "Evidence", "Application"],
                campaign_goals=["Improve qualified audience understanding"],
            ),
            ProviderCapability.REVIEW: ReviewOutput(
                approved=True,
                score=80,
                findings=["Deterministic review requires human confirmation."],
            ),
            ProviderCapability.IMAGE_PROMPT: ImagePromptOutput(
                prompt=f"Original editorial visual representing {label}.",
                exclusions=["logos", "copyrighted characters"],
            ),
            ProviderCapability.VIDEO_PROMPT: VideoPromptOutput(
                prompt=f"Original explanatory sequence for {label}.",
                shot_guidance=["Readable framing", "Accessible pacing"],
            ),
            ProviderCapability.METADATA: MetadataOutput(
                title=f"Guide to {label}",
                description=f"A practical overview of {label}.",
                tags=[label],
            ),
            ProviderCapability.AUDIENCE: AudienceOutput(
                persona_name="Practical learner",
                needs=[f"Understand {label}"],
                objections=["Unsupported claims"],
            ),
            ProviderCapability.ANALYTICS: AnalyticsAdviceOutput(
                observations=["Use explicitly supplied metrics only."],
                recommendations=["Compare like-for-like content periods."],
            ),
            ProviderCapability.SCENE: SceneOutput(
                scene_prompts=[f"Original scene explaining {label}."],
            ),
            ProviderCapability.ANIMATION: AnimationOutput(
                motion_prompts=[f"Subtle accessible motion for {label}."],
            ),
            ProviderCapability.FLOW: FlowOutput(
                message=(
                    "Flow is an interface placeholder; no implementation "
                    "or request occurred."
                ),
            ),
        }
        return outputs[capability]
