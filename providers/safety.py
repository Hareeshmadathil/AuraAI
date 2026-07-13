"""Provider prompt and response validation without retaining content."""

from __future__ import annotations

import json
import re

from providers.exceptions import ProviderValidationError
from providers.models import (
    AnalyticsAdviceOutput, AnimationOutput, AudienceOutput, HookOutput,
    ImagePromptOutput, MarketingOutput, MetadataOutput, ProviderCapability,
    ProviderOutput, ResearchOutput, ReviewOutput, SEOOutput, SceneOutput,
    ScriptOutput, StoryOutput, VideoPromptOutput, FlowOutput,
)
from providers.prompt_template import ProviderPrompt
from providers.provider_result import ProviderResult


_SECRET_PATTERN = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|client[_-]?secret|password)\s*[:=]"
)

_OUTPUT_TYPES: dict[ProviderCapability, type] = {
    ProviderCapability.RESEARCH: ResearchOutput,
    ProviderCapability.SCRIPT: ScriptOutput,
    ProviderCapability.HOOK: HookOutput,
    ProviderCapability.STORY: StoryOutput,
    ProviderCapability.SEO: SEOOutput,
    ProviderCapability.MARKETING: MarketingOutput,
    ProviderCapability.REVIEW: ReviewOutput,
    ProviderCapability.IMAGE_PROMPT: ImagePromptOutput,
    ProviderCapability.VIDEO_PROMPT: VideoPromptOutput,
    ProviderCapability.METADATA: MetadataOutput,
    ProviderCapability.AUDIENCE: AudienceOutput,
    ProviderCapability.ANALYTICS: AnalyticsAdviceOutput,
    ProviderCapability.SCENE: SceneOutput,
    ProviderCapability.ANIMATION: AnimationOutput,
    ProviderCapability.FLOW: FlowOutput,
}


class SafetyValidator:
    """Reject likely credentials in prompts and provider responses."""

    def validate_prompt(self, prompt: ProviderPrompt) -> None:
        if _SECRET_PATTERN.search(prompt.text):
            raise ProviderValidationError("Prompt contains credential-like data.")

    def validate_response(self, output: ProviderOutput) -> None:
        serialized = json.dumps(output.model_dump(mode="json"), sort_keys=True)
        if _SECRET_PATTERN.search(serialized):
            raise ProviderValidationError("Provider response contains unsafe data.")


class ResponseValidator:
    """Require the output model associated with the requested capability."""

    def validate(
        self,
        capability: ProviderCapability,
        result: ProviderResult[ProviderOutput],
    ) -> ProviderResult[ProviderOutput]:
        expected = _OUTPUT_TYPES[capability]
        if not isinstance(result.output, expected):
            raise ProviderValidationError(
                "Provider returned an output model for a different capability.",
                provider_name=result.provider,
            )
        return result
