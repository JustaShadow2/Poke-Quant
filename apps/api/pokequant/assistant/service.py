"""AI Assistant service: grounded tool-calling over platform data.

The assistant can answer questions about instruments by looking up scores,
forecasts, risk, explanations, and prices. It never invents data — all facts
come from the platform's computed outputs.

Architecture:
- User sends a question.
- We gather relevant context (instrument data, scores, forecasts, risk).
- We compose a system prompt with the context.
- Groq generates a grounded response.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from pokequant.assistant.llm import GroqClient
from pokequant.core.logging import get_logger
from pokequant.repositories.catalog import CatalogRepository
from pokequant.repositories.market import SnapshotRepository
from pokequant.repositories.ml_repo import PredictionRepository
from pokequant.repositories.phase2_repo import (
    ExplanationRepository,
    RiskRepository,
    ScoreRepository,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are the PokéQuant Research Assistant — an AI that helps users research Pokémon sealed product investments.

RULES:
- Only state facts from the provided context data. Never invent prices, scores, or forecasts.
- If data is unavailable, say so clearly.
- Be concise and direct. Use numbers from the context.
- Always note that this is research, not investment advice.
- When discussing forecasts, mention they are model estimates with uncertainty.
- Reference specific features/drivers from SHAP explanations when available.

You have access to the following data about instruments in the platform:
{context}

Answer the user's question based ONLY on the above data."""


@dataclass
class AssistantResponse:
    answer: str
    model_used: Optional[str] = None
    context_instruments: list[str] = None  # type: ignore[assignment]
    grounded: bool = True

    def __post_init__(self) -> None:
        if self.context_instruments is None:
            self.context_instruments = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "model_used": self.model_used,
            "context_instruments": self.context_instruments,
            "grounded": self.grounded,
        }


class AssistantService:
    """AI Research Assistant backed by Groq."""

    def __init__(self, session: Session, groq_client: GroqClient) -> None:
        self.session = session
        self.groq = groq_client
        self.catalog = CatalogRepository(session)
        self.snapshots = SnapshotRepository(session)
        self.predictions = PredictionRepository(session)
        self.scores = ScoreRepository(session)
        self.risks = RiskRepository(session)
        self.explanations = ExplanationRepository(session)

    def answer(self, question: str, *, owner_id: str = "default") -> AssistantResponse:
        """Answer a user question with grounded platform data."""
        # Gather context from all instruments.
        context_parts: list[str] = []
        context_instruments: list[str] = []

        instruments = self.catalog.all_active("pokemon")
        for inst in instruments[:15]:  # Cap to avoid token overflow
            parts: list[str] = []
            parts.append(f"**{inst.name}** ({inst.symbol}, ID: {inst.id})")

            # Latest price.
            latest = self.snapshots.latest(inst.id)
            if latest:
                parts.append(f"  Price: ${float(latest.price_usd):.2f}")

            # Forecast.
            pred = self.predictions.latest(inst.id, "d90")
            if pred:
                parts.append(
                    f"  90d Forecast: ${float(pred.predicted_price):.2f} "
                    f"(return: {pred.predicted_return*100:.1f}%)"
                )

            # Score.
            score = self.scores.latest(inst.id, "d90")
            if score:
                parts.append(f"  Score: {score.score:.0f} ({score.band})")

            # Risk.
            risk = self.risks.latest(inst.id, "d90")
            if risk:
                parts.append(f"  Risk: {risk.overall_score:.0f}/100 ({risk.overall_level})")

            # Explanation.
            explanation = self.explanations.latest(inst.id, "d90")
            if explanation and explanation.narrative:
                parts.append(f"  Why: {explanation.narrative}")

            if len(parts) > 1:  # Has data beyond the name.
                context_parts.append("\n".join(parts))
                context_instruments.append(str(inst.id))

        context = "\n\n".join(context_parts) if context_parts else "No instrument data available."

        # Compose messages.
        system_msg = SYSTEM_PROMPT.format(context=context)
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": question},
        ]

        # Call Groq.
        response = self.groq.chat(messages, temperature=0.3, max_tokens=800)

        if response is None:
            return AssistantResponse(
                answer="I'm unable to respond right now — all models are at capacity. Please try again in a moment.",
                model_used=None,
                context_instruments=context_instruments,
                grounded=False,
            )

        return AssistantResponse(
            answer=response,
            model_used=self.groq.models[0],  # Will refine to track actual model used
            context_instruments=context_instruments,
            grounded=True,
        )
