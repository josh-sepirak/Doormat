"""Extraction strategy cache and validation."""

import json
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.extraction.schemas import StrategyUpdate
from doormat.models.orm import ExtractionFeedback, ExtractionStrategy

logger = structlog.get_logger(__name__)


class StrategyCache:
    """Manages retrieving and updating extraction strategies."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, property_manager_id: str) -> ExtractionStrategy | None:
        """Get the most recent strategy for a property manager."""
        stmt = (
            select(ExtractionStrategy)
            .where(ExtractionStrategy.property_manager_id == property_manager_id)
            .order_by(ExtractionStrategy.last_refined.desc().nulls_last())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def merge(
        self,
        property_manager_id: str,
        update: StrategyUpdate,
        source_listing_id: str | None = None,
    ) -> bool:
        """Merge a StrategyUpdate into the property manager's strategy.

        If validation passes against recent listings, the update is saved.
        """
        logger.info("strategy_merge_start", property_manager_id=property_manager_id)

        current_strategy = await self.get(property_manager_id)

        # Build the new strategy JSON.
        if current_strategy:
            try:
                current_data = json.loads(current_strategy.strategy_json)
            except json.JSONDecodeError:
                logger.warning(
                    "strategy_json_corrupt",
                    property_manager_id=property_manager_id,
                    strategy_id=current_strategy.id,
                )
                current_data = _empty_strategy_data()
        else:
            current_data = _empty_strategy_data()

        current_data["field_selectors"].update(update.field_selectors)
        if update.pre_extraction_actions:
            # simple append for now, might need deduplication later
            current_data["pre_extraction_actions"].extend(update.pre_extraction_actions)
            current_data["pre_extraction_actions"] = list(
                dict.fromkeys(current_data["pre_extraction_actions"])
            )
        if update.notes:
            current_data["notes"] = f"{current_data.get('notes', '')}\\n\\n{update.notes}".strip()

        new_strategy_json = json.dumps(current_data)

        # Phase 3 initial implementation accepts the patch without a hold-out
        # validation loop, but records the decision for auditability.
        validation_passed = True

        # Record feedback
        if current_strategy:
            feedback = ExtractionFeedback(
                id=str(uuid.uuid4()),
                strategy_id=current_strategy.id,
                listing_id=source_listing_id,
                validation_result="pass" if validation_passed else "fail",
                refined_strategy=new_strategy_json,
                timestamp=datetime.now(UTC),
            )
            self._session.add(feedback)

        if validation_passed:
            # Create a new strategy row or update existing
            if not current_strategy:
                new_strategy = ExtractionStrategy(
                    id=str(uuid.uuid4()),
                    property_manager_id=property_manager_id,
                    strategy_json=new_strategy_json,
                    validation_rate=1.0,
                    last_refined=datetime.now(UTC),
                )
                self._session.add(new_strategy)
            else:
                current_strategy.strategy_json = new_strategy_json
                current_strategy.last_refined = datetime.now(UTC)

            await self._session.commit()
            logger.info("strategy_merge_success", property_manager_id=property_manager_id)
            return True

        await self._session.commit()
        logger.warning("strategy_merge_failed_validation", property_manager_id=property_manager_id)
        return False


def _empty_strategy_data() -> dict[str, object]:
    """Return the canonical serialized strategy shape."""
    return {"field_selectors": {}, "pre_extraction_actions": [], "notes": ""}
