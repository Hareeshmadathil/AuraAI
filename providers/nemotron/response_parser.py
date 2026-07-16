"""Strict final-answer extraction for OpenAI-compatible Nemotron responses."""
from __future__ import annotations

import json
import re
from typing import Any

from providers.exceptions import ProviderValidationError
from providers.nemotron.models import NemotronResponseShape

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_FINAL_FIELDS = ("final_answer", "final", "output_text")
_REASONING_FIELDS = ("reasoning", "reasoning_content", "analysis")


def _failure(code: str, message: str) -> ProviderValidationError:
    return ProviderValidationError(message, provider_name="nemotron",
        details={"safe_error_code": code, "validation_stage": "structured_output",
                 "parser_stage": "final_answer_extraction", "transport_completed": True},
        retryable=False)


class NemotronJsonExtractor:
    """Extract exactly one bounded JSON object without executing content."""

    def __init__(self, maximum_characters: int = 2_000_000) -> None:
        self.maximum_characters = maximum_characters

    def extract(self, value: object) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            raise _failure("STRUCTURED_OUTPUT_INCOMPATIBLE", "Nemotron final answer was not a JSON object or string.")
        if len(value) > self.maximum_characters:
            raise _failure("MALFORMED_PROVIDER_RESPONSE", "Nemotron final answer exceeded the safe size limit.")
        cleaned = value.strip()
        if not cleaned:
            raise _failure("EMPTY_FINAL_ANSWER", "Nemotron final answer was empty.")
        fences = _FENCE.findall(cleaned)
        if fences:
            if len(fences) != 1 or _FENCE.sub("", cleaned).strip():
                raise _failure("STRUCTURED_OUTPUT_INCOMPATIBLE", "Nemotron final answer contained ambiguous fenced content.")
            return self._decode(fences[0])
        try:
            decoded = json.loads(cleaned)
            if isinstance(decoded, dict):
                return decoded
        except json.JSONDecodeError:
            pass
        objects: list[dict[str, Any]] = []
        decoder = json.JSONDecoder()
        index = 0
        while index < len(cleaned):
            index = cleaned.find("{", index)
            if index < 0:
                break
            try:
                candidate, consumed = decoder.raw_decode(cleaned[index:])
            except json.JSONDecodeError:
                index += 1
                continue
            if isinstance(candidate, dict) and candidate not in objects:
                objects.append(candidate)
            index += max(consumed, 1)
        if len(objects) == 1:
            return objects[0]
        code = "MALFORMED_PROVIDER_RESPONSE" if not objects else "STRUCTURED_OUTPUT_INCOMPATIBLE"
        raise _failure(code, "Nemotron final answer did not contain one unambiguous JSON object.")

    @staticmethod
    def _decode(value: str) -> dict[str, Any]:
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as error:
            raise _failure("MALFORMED_PROVIDER_RESPONSE", "Nemotron final answer contained malformed JSON.") from error
        if not isinstance(decoded, dict):
            raise _failure("STRUCTURED_OUTPUT_INCOMPATIBLE", "Nemotron final answer must be a JSON object.")
        return decoded


class NemotronResponseParser:
    """Select only a documented final-answer field and ignore reasoning."""

    def __init__(self, extractor: NemotronJsonExtractor | None = None) -> None:
        self.extractor = extractor or NemotronJsonExtractor()

    def parse_envelope(self, envelope: dict[str, Any], *, http_status_class: str) -> tuple[dict[str, Any], NemotronResponseShape, str]:
        choices = envelope.get("choices")
        choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        reasoning = next((message.get(name) for name in _REASONING_FIELDS if message.get(name) is not None), None)
        content = message.get("content")
        field = "message.content"
        final_value = self._content_value(content)
        if final_value is None:
            for name in _FINAL_FIELDS:
                if message.get(name) is not None:
                    final_value = message[name]; field = f"message.{name}"; break
        shape = self._shape(envelope, choices, message, content, reasoning, choice, http_status_class)
        if final_value is None or (isinstance(final_value, str) and not final_value.strip()):
            code = "PROVIDER_REASONING_WITHOUT_FINAL_ANSWER" if reasoning else "EMPTY_FINAL_ANSWER"
            raise _failure(code, "Nemotron did not return a usable final answer.")
        return self.extractor.extract(final_value), shape, field

    @staticmethod
    def _content_value(content: object) -> object | None:
        if isinstance(content, (str, dict)):
            return content
        if isinstance(content, list):
            values = []
            for part in content:
                if not isinstance(part, dict) or part.get("type") not in {"text", "output_text"}:
                    continue
                value = part.get("text")
                if isinstance(value, str): values.append(value)
            return "".join(values) if values else None
        return None

    @staticmethod
    def _shape(envelope, choices, message, content, reasoning, choice, status) -> NemotronResponseShape:
        usage=envelope.get("usage") if isinstance(envelope.get("usage"), dict) else {}
        safe_usage={key:int(value) for key,value in usage.items() if key in {"prompt_tokens","completion_tokens","total_tokens"} and isinstance(value,int)}
        kind = "null" if content is None else type(content).__name__
        count = len(content) if isinstance(content, str) else 0
        reasoning_count = len(reasoning) if isinstance(reasoning, str) else 0
        return NemotronResponseShape(top_level_keys=sorted(envelope), choices_count=len(choices) if isinstance(choices,list) else 0,
            message_keys=sorted(message), message_value_types={key:type(value).__name__ for key,value in message.items()},
            content_kind=kind, content_character_count=count, reasoning_field_present=reasoning is not None,
            reasoning_character_count=reasoning_count, finish_reason=choice.get("finish_reason") if isinstance(choice.get("finish_reason"),str) else None,
            usage=safe_usage, http_status_class=status)
