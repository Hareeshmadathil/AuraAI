"""Typed Gemini prompt builder that remains vendor-isolated."""

from providers.prompt_template import PromptTemplate, PromptVariable, ProviderPrompt


class GeminiPromptBuilder:
    def build(
        self,
        template: PromptTemplate,
        variables: list[PromptVariable],
    ) -> ProviderPrompt:
        return template.render(variables)
