"""Extraction strategy cache and validation."""

import json
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.extraction.recipe_validator import RecipeValidator
from doormat.extraction.schemas import ApiRecipe, ExtractedListing, StrategyUpdate
from doormat.models.orm import ExtractionFeedback, ExtractionStrategy, Listing

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
        
        # Validate recipe if provided
        api_recipe = None
        validation_passed = True
        
        if update.api_recipe:
            logger.info(
                "recipe_validation_start",
                property_manager_id=property_manager_id,
                recipe_confidence=update.api_recipe.confidence,
            )
            
            # Try to validate recipe against held-out listings
            held_out_listings = await self._select_held_out_listings(
                property_manager_id, sample_size=5
            )
            
            if held_out_listings:
                validator = RecipeValidator()
                validation_result = await validator.validate_recipe(
                    update.api_recipe, held_out_listings
                )
                
                if validation_result.passed:
                    logger.info(
                        "recipe_validation_passed",
                        property_manager_id=property_manager_id,
                        matched_count=validation_result.matched_count,
                        total_count=validation_result.total_count,
                    )
                    api_recipe = update.api_recipe
                else:
                    logger.warning(
                        "recipe_validation_failed",
                        property_manager_id=property_manager_id,
                        reason=validation_result.failure_reason,
                    )
                    validation_passed = False
            else:
                # No held-out listings to validate against; accept recipe on confidence
                if update.api_recipe.confidence in ["high", "medium"]:
                    logger.info(
                        "recipe_promoted_no_holdout",
                        property_manager_id=property_manager_id,
                        confidence=update.api_recipe.confidence,
                    )
                    api_recipe = update.api_recipe
                else:
                    logger.warning(
                        "recipe_rejected_low_confidence_no_holdout",
                        property_manager_id=property_manager_id,
                        confidence=update.api_recipe.confidence,
                    )

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
                    api_recipe_json=api_recipe.model_dump_json() if api_recipe else None,
                    validation_rate=1.0,
                    last_refined=datetime.now(UTC),
                )
                self._session.add(new_strategy)
            else:
                current_strategy.strategy_json = new_strategy_json
                current_strategy.api_recipe_json = api_recipe.model_dump_json() if api_recipe else current_strategy.api_recipe_json
                current_strategy.last_refined = datetime.now(UTC)

            await self._session.commit()
            logger.info("strategy_merge_success", property_manager_id=property_manager_id)
            return True

        await self._session.commit()
        logger.warning("strategy_merge_failed_validation", property_manager_id=property_manager_id)
        return False
    
    async def _select_held_out_listings(
        self, property_manager_id: str, sample_size: int = 5
    ) -> list[ExtractedListing]:
        """Select recent listings for recipe validation (held-out sample)."""
        stmt = (
            select(Listing)
            .join(ExtractionStrategy)
            .where(ExtractionStrategy.property_manager_id == property_manager_id)
            .order_by(desc(Listing.extracted_at))
            .limit(sample_size)
        )
        result = await self._session.execute(stmt)
        listings_orm = result.scalars().all()
        
        extracted_listings = []
        for listing_orm in listings_orm:
            try:
                extracted = ExtractedListing(
                    address=listing_orm.address,
                    rent=int(listing_orm.price) if listing_orm.price else 0,
                    bedrooms=listing_orm.bedrooms,
                    bathrooms=listing_orm.bathrooms,
                    url=listing_orm.url,
                    source_id=listing_orm.source_id,
                    extracted_at=listing_orm.extracted_at or datetime.now(UTC),
                )
                extracted_listings.append(extracted)
            except (ValueError, AttributeError):
                continue
        
        return extracted_listings


def _empty_strategy_data() -> dict[str, object]:
    """Return the canonical serialized strategy shape."""
    return {
        "field_selectors": {},
        "pre_extraction_actions": [],
        "notes": "",
        "api_recipe": None,
    }
