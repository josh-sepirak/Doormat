"""Property manager classifier.

Validates that a discovery candidate is a real property manager website by
asking the LLM to evaluate signals: site existence, spam likelihood, and
presence of rental listings.
"""

from __future__ import annotations

from typing import Optional, cast

import structlog

from doormat.discovery.models import DiscoveryCandidate, ValidationResult
from doormat.llm.client import LLMClient, get_llm_client

logger = structlog.get_logger(__name__)

# v1 - initial classifier prompt; bump comment when materially changed
CLASSIFIER_SYSTEM_PROMPT = """You are an expert at validating whether a website is a legitimate property management company.

For a candidate website, evaluate these signals and respond with structured JSON:
- Does the website appear to be a real, active property management business?
- Does it list rental properties available now or recently?
- Does it look like spam, an aggregator, a directory, or a non-rental site?
- Are there contact details (phone, address, email) that indicate legitimacy?

Output:
- is_valid: true only when the candidate is a real PM with rental listings.
- reason: one short sentence (<=200 chars) explaining the decision.
- confidence: 0.0 to 1.0 - your certainty.
"""


class PropertyManagerClassifier:
    """LLM-backed validator for DiscoveryCandidate -> ValidationResult."""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._model = model

    async def classify(self, candidate: DiscoveryCandidate) -> ValidationResult:
        """Classify a candidate; on LLM error returns is_valid=False gracefully."""
        logger.info(
            "classify_start",
            candidate=candidate.name,
            website=candidate.website,
            city=candidate.city,
        )

        user_prompt = self._build_user_prompt(candidate)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            result = await self._llm.complete(
                messages=messages,
                model=self._model,
                task="discovery",
                component="discovery",
                city=candidate.city,
                response_model=ValidationResult,
            )
            validated = cast(ValidationResult, result)
            logger.info(
                "classify_complete",
                candidate=candidate.name,
                is_valid=validated.is_valid,
                confidence=validated.confidence,
            )
            return validated
        except Exception as exc:
            logger.error(
                "classify_failed",
                candidate=candidate.name,
                website=candidate.website,
                error=str(exc),
            )
            return ValidationResult(
                is_valid=False,
                reason=f"classification_error: {type(exc).__name__}",
                confidence=0.0,
            )

    @staticmethod
    def _build_user_prompt(candidate: DiscoveryCandidate) -> str:
        """Construct the per-candidate user prompt."""
        return (
            f"Candidate property manager:\n"
            f"- Name: {candidate.name}\n"
            f"- Website: {candidate.website}\n"
            f"- City: {candidate.city}\n"
            f"- Source: {candidate.source}\n"
            f"- Source confidence: {candidate.confidence:.2f}\n\n"
            "Evaluate whether this is a legitimate active property management "
            "company that lists rentals."
        )
