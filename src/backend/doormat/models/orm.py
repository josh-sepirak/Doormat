"""SQLAlchemy ORM models with strict typing."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from doormat.db.base import Base


class Preference(Base):
    """User search preferences."""

    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)  # Natural language
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    listings: Mapped[list["Listing"]] = relationship(back_populates="preference")

    __table_args__ = (Index("idx_city_created", "city", "created_at"),)


class PropertyManager(Base):
    """Discovered property managers (discovery cache)."""

    __tablename__ = "property_managers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    listing_page_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validated: Mapped[bool] = mapped_column(Boolean, default=False)
    discovery_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    # Relationships
    extraction_strategies: Mapped[list["ExtractionStrategy"]] = relationship(
        back_populates="property_manager"
    )
    listings: Mapped[list["Listing"]] = relationship(back_populates="property_manager")

    __table_args__ = (Index("idx_city_validated", "city", "validated"),)


class ExtractionStrategy(Base):
    """LLM-generated extraction strategies (scrapers)."""

    __tablename__ = "extraction_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_manager_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_managers.id"), nullable=False, index=True
    )
    strategy_json: Mapped[str] = mapped_column(Text, nullable=False)  # LLM output
    tier1_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tier2_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    validation_rate: Mapped[float] = mapped_column(Float, default=0.95)
    last_refined: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    property_manager: Mapped[PropertyManager] = relationship(back_populates="extraction_strategies")
    feedback: Mapped[list["ExtractionFeedback"]] = relationship(back_populates="strategy")

    __table_args__ = (Index("idx_manager_refined", "property_manager_id", "last_refined"),)


class Listing(Base):
    """Extracted and scored rental listings."""

    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_manager_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_managers.id"), nullable=False, index=True
    )
    preference_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("preferences.id"), nullable=True, index=True
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bathrooms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    pets_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    amenities: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # JSON list stored as text
    photos: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list stored as text
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON stored as text
    extraction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    extraction_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tier1_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tier2_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    validation_passed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    property_manager: Mapped[PropertyManager] = relationship(back_populates="listings")
    preference: Mapped[Optional[Preference]] = relationship(back_populates="listings")

    __table_args__ = (
        Index("idx_manager_timestamp", "property_manager_id", "extraction_timestamp"),
        Index("idx_price", "price"),
    )


class Cost(Base):
    """LLM calls and API usage tracking."""

    __tablename__ = "costs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    component: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    __table_args__ = (Index("idx_component_timestamp", "component", "timestamp"),)


class ExtractionFeedback(Base):
    """Validation results for extraction refinement."""

    __tablename__ = "extraction_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("extraction_strategies.id"), nullable=False, index=True
    )
    listing_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("listings.id"), nullable=True, index=True
    )
    validation_result: Mapped[str] = mapped_column(String(50), nullable=False)  # pass|fail|partial
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refined_strategy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    # Relationships
    strategy: Mapped[ExtractionStrategy] = relationship(back_populates="feedback")

    __table_args__ = (Index("idx_strategy_timestamp", "strategy_id", "timestamp"),)
