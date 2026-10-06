"""Alert rules and evaluation engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from pokequant.db.models import AlertEvent, AlertRule

# Rule types and their evaluation logic.
RULE_TYPES = ("price_above", "price_below", "score_above", "score_below", "risk_above")

# Cooldown: don't re-fire the same rule within this window.
COOLDOWN = timedelta(hours=12)


class AlertService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_rule(
        self,
        owner_id: str,
        instrument_id: uuid.UUID,
        rule_type: str,
        threshold: float,
    ) -> AlertRule:
        rule = AlertRule(
            owner_id=owner_id,
            instrument_id=instrument_id,
            rule_type=rule_type,
            threshold=threshold,
        )
        self.session.add(rule)
        self.session.flush()
        return rule

    def list_rules(self, owner_id: str) -> list[AlertRule]:
        stmt = (
            select(AlertRule)
            .where(AlertRule.owner_id == owner_id)
            .order_by(AlertRule.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def delete_rule(self, rule_id: uuid.UUID) -> None:
        rule = self.session.get(AlertRule, rule_id)
        if rule:
            self.session.delete(rule)

    def toggle_rule(self, rule_id: uuid.UUID, active: bool) -> None:
        self.session.execute(
            update(AlertRule).where(AlertRule.id == rule_id).values(is_active=active)
        )

    def evaluate_all(self, data: dict[str, dict[str, float]]) -> list[AlertEvent]:
        """Evaluate all active rules against current data.

        Args:
            data: {instrument_id_str: {"price": float, "score": float, "risk": float}}

        Returns:
            List of newly fired alert events.
        """
        now = datetime.utcnow()
        stmt = select(AlertRule).where(AlertRule.is_active == True)  # noqa: E712
        rules = list(self.session.execute(stmt).scalars().all())

        fired: list[AlertEvent] = []
        for rule in rules:
            # Cooldown check.
            if rule.last_triggered_at and (now - rule.last_triggered_at) < COOLDOWN:
                continue

            iid = str(rule.instrument_id)
            instrument_data = data.get(iid, {})
            current_value = self._get_value(rule.rule_type, instrument_data)
            if current_value is None:
                continue

            if self._condition_met(rule.rule_type, current_value, rule.threshold):
                message = self._make_message(rule.rule_type, current_value, rule.threshold)
                event = AlertEvent(
                    rule_id=rule.id,
                    instrument_id=rule.instrument_id,
                    message=message,
                    current_value=current_value,
                )
                self.session.add(event)
                rule.last_triggered_at = now
                fired.append(event)

        self.session.flush()
        return fired

    def get_events(self, owner_id: str, unread_only: bool = False) -> list[AlertEvent]:
        stmt = (
            select(AlertEvent)
            .join(AlertRule)
            .where(AlertRule.owner_id == owner_id)
        )
        if unread_only:
            stmt = stmt.where(AlertEvent.is_read == False)  # noqa: E712
        stmt = stmt.order_by(AlertEvent.fired_at.desc()).limit(50)
        return list(self.session.execute(stmt).scalars().all())

    def mark_read(self, event_id: uuid.UUID) -> None:
        self.session.execute(
            update(AlertEvent).where(AlertEvent.id == event_id).values(is_read=True)
        )

    def _get_value(self, rule_type: str, data: dict[str, float]) -> Optional[float]:
        if "price" in rule_type:
            return data.get("price")
        if "score" in rule_type:
            return data.get("score")
        if "risk" in rule_type:
            return data.get("risk")
        return None

    def _condition_met(self, rule_type: str, value: float, threshold: float) -> bool:
        if rule_type.endswith("_above"):
            return value >= threshold
        if rule_type.endswith("_below"):
            return value <= threshold
        return False

    def _make_message(self, rule_type: str, value: float, threshold: float) -> str:
        action = "crossed above" if rule_type.endswith("_above") else "dropped below"
        metric = rule_type.rsplit("_", 1)[0].replace("_", " ")
        return f"{metric.capitalize()} {action} {threshold:.2f} (current: {value:.2f})"
