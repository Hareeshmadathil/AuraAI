"""Meaningful deterministic script generation without an LLM."""

from __future__ import annotations

from production.models import ContentBrief, ScriptSection, VideoScript


class ScriptEngine:
    """Create an educational script solely from a validated brief."""

    def build(self, brief: ContentBrief) -> VideoScript:
        """Create a readable script with explicit verification markers."""

        value = brief.production_input
        source_context = (
            " Supplied context includes: " + "; ".join(value.source_notes) + "."
            if value.source_notes
            else " No external evidence was supplied, so examples remain illustrative."
        )
        section_specs = [
            (
                "hook",
                "The costly friction",
                0.10,
                f"If {value.audience_problem.lower()}, the answer is not another "
                f"vague promise. In this guide, we will examine {value.topic}, show "
                f"a practical starting point, and explain what still needs human "
                f"judgment. The goal is simple: {value.audience_promise}",
                "Open loop: a practical three-part framework follows.",
            ),
            (
                "context",
                "What the idea actually means",
                0.15,
                f"Start with a useful definition. {value.topic} is a way to improve "
                f"a repeatable task, not a substitute for ownership or review. For "
                f"{value.target_audience}, the best opportunity is usually a narrow "
                f"workflow with a clear input, a review checkpoint, and a measurable "
                f"output.{source_context}",
                "Reset attention with a plain-language definition.",
            ),
            (
                "framework",
                "Step one: find the repeatable bottleneck",
                0.18,
                f"List the recurring work behind {value.audience_problem.lower()}. "
                "Choose one task that happens often, consumes attention, and can be "
                "checked before its result affects a customer. Record the current "
                "steps, owner, time cost, and failure conditions. This baseline keeps "
                "the improvement honest and prevents a tool from becoming the goal.",
                "Pattern interrupt: replace tool-first thinking with a workflow map.",
            ),
            (
                "framework",
                "Step two: design a safe assisted workflow",
                0.20,
                f"Use {value.primary_keyword} naturally inside a controlled process. "
                "Define the approved source material, the expected output format, and "
                "the person responsible for review. Keep sensitive information out of "
                "unapproved systems. Test with low-risk examples, document exceptions, "
                "and stop when the output cannot be verified. Assistance should make "
                "good judgment easier to apply, not easier to skip.",
                "Show a three-box input, draft, review sequence.",
            ),
            (
                "example",
                "Step three: measure the useful change",
                0.17,
                f"Compare the new process with the baseline. Look at time saved, "
                "corrections required, consistency, and whether the audience outcome "
                f"supports {value.campaign_goal.lower()}. Treat every number as a local "
                "observation unless a supplied source supports a broader claim. A small "
                "reliable gain is more valuable than a dramatic result that cannot be "
                "repeated or explained.",
                "Invite the viewer to predict which metric will change first.",
            ),
            (
                "limitations",
                "What this approach cannot promise",
                0.12,
                "No workflow guarantees revenue, reach, accuracy, or eligibility for "
                "a platform program. Results depend on the starting process, input "
                "quality, review discipline, customer needs, and changing provider "
                "rules. Verify financial, legal, medical, security, and platform claims "
                "with appropriate current sources before acting or publishing.",
                "Credibility reset: state limitations before the conclusion.",
            ),
            (
                "conclusion",
                "Your next responsible action",
                0.08,
                f"Choose one low-risk workflow, write down its current baseline, and "
                "test one assisted step with human review. Keep what is measurable, "
                "remove what creates hidden work, and document what you learn. "
                f"{value.preferred_call_to_action}",
                "Close the opening loop with one concrete next action.",
            ),
        ]
        durations = self._allocate_durations(
            value.target_duration_seconds,
            [spec[2] for spec in section_specs],
        )
        claims = list(value.source_notes) or [
            "Any time-saving or performance claim must be verified before publication."
        ]
        sections = [
            ScriptSection(
                section_type=spec[0],
                title=spec[1],
                purpose=f"Advance the {spec[0]} stage of the viewer journey.",
                narration=spec[3],
                estimated_duration_seconds=duration,
                visual_intent=(
                    f"Use {brief.selected_style.value.replace('_', ' ')} visuals to "
                    f"clarify {spec[1].lower()} without depicting generated media as real."
                ),
                retention_device=spec[4],
                source_notes=list(value.source_notes),
                claims_requiring_verification=(
                    claims if spec[0] in {"context", "example", "limitations"} else []
                ),
            )
            for spec, duration in zip(section_specs, durations, strict=True)
        ]
        word_count = sum(len(section.narration.split()) for section in sections)
        return VideoScript(
            brief_id=brief.brief_id,
            title=value.working_title,
            hook=sections[0].narration,
            sections=sections,
            call_to_action=value.preferred_call_to_action,
            total_estimated_duration_seconds=sum(durations),
            word_count=word_count,
            primary_keyword=value.primary_keyword,
            secondary_keywords=list(value.secondary_keywords),
            disclaimer_notes=[
                "This deterministic draft requires factual review before publication.",
                "No result, revenue, or platform outcome is guaranteed.",
            ],
            sample_data=value.sample_data,
        )

    @staticmethod
    def _allocate_durations(total: float, weights: list[float]) -> list[float]:
        """Allocate a total duration while avoiding rounding drift."""

        durations = [round(total * weight, 2) for weight in weights[:-1]]
        durations.append(round(total - sum(durations), 2))
        return durations
