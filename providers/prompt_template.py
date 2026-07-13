"""Versioned prompts built from explicit, typed variables."""

from __future__ import annotations

from enum import StrEnum
from string import Formatter

from pydantic import Field, model_validator

from core import AuraBaseModel


class PromptCategory(StrEnum):
    RESEARCH = "research"
    CREATION = "creation"
    REVIEW = "review"
    STRATEGY = "strategy"
    ANALYTICS = "analytics"


class PromptSafetyLevel(StrEnum):
    STANDARD = "standard"
    RESTRICTED = "restricted"


class PromptVariable(AuraBaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: str = Field(min_length=1, max_length=10000)


class ProviderPrompt(AuraBaseModel):
    """Rendered prompt plus metadata; never logged by the provider layer."""

    text: str = Field(min_length=1, max_length=30000)
    category: PromptCategory
    version: str = Field(pattern=r"^v\d+(?:\.\d+)*$")
    safety_level: PromptSafetyLevel = PromptSafetyLevel.STANDARD
    template_name: str = Field(min_length=1, max_length=150)
    variable_names: list[str] = Field(default_factory=list)


class PromptTemplate(AuraBaseModel):
    name: str = Field(min_length=1, max_length=150)
    template: str = Field(min_length=1, max_length=30000)
    category: PromptCategory
    version: str = Field(default="v1", pattern=r"^v\d+(?:\.\d+)*$")
    safety_level: PromptSafetyLevel = PromptSafetyLevel.STANDARD

    @model_validator(mode="after")
    def validate_fields(self) -> "PromptTemplate":
        names = [name for _, name, _, _ in Formatter().parse(self.template) if name]
        if len(names) != len(set(names)):
            raise ValueError("Prompt placeholders must be unique.")
        return self

    def render(self, variables: list[PromptVariable]) -> ProviderPrompt:
        values = {item.name: item.value for item in variables}
        expected = {
            name for _, name, _, _ in Formatter().parse(self.template) if name
        }
        if set(values) != expected:
            raise ValueError("Prompt variables must exactly match the template.")
        return ProviderPrompt(
            text=self.template.format(**values),
            category=self.category,
            version=self.version,
            safety_level=self.safety_level,
            template_name=self.name,
            variable_names=sorted(values),
        )


def build_department_prompt(
    template_name: str,
    category: PromptCategory,
    subject: str,
) -> ProviderPrompt:
    """Build the shared minimal advisory prompt used by employees."""

    template = PromptTemplate(
        name=template_name,
        template="Provide a typed, safety-conscious advisory for: {subject}",
        category=category,
        version="v1",
    )
    return template.render([PromptVariable(name="subject", value=subject)])
