"""SQLAlchemy ORM models with strict typing."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from doormat.db.base import Base


class Preference(Base):
    """User search preferences."""

    __tablename__ = "preferences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)  # Natural language
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    api_provider: Mapped[str] = mapped_column(String(50), default="openrouter")
    openrouter_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    apify_api_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fast_model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    smart_model: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    # JSON list of enabled listing sources, e.g. ["craigslist", "zillow", "facebook"]
    sources_enabled: Mapped[str] = mapped_column(Text, nullable=False, default='["craigslist"]')
    # LLM prompt key -> custom text (defaults live in code only).
    prompt_overrides: Mapped[Optional[dict[str, str]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    listings: Mapped[list["Listing"]] = relationship(back_populates="preference")

    __table_args__ = (Index("idx_city_created", "city", "created_at"),)

    @property
    def has_openrouter_api_key(self) -> bool:
        """Expose key presence without returning the secret."""
        from doormat.security.secrets import has_secret

        return has_secret(self.openrouter_api_key)

    @property
    def openrouter_key_last4(self) -> Optional[str]:
        """Expose a masked key hint for the UI."""
        from doormat.security.secrets import secret_last4

        return secret_last4(self.openrouter_api_key)

    @property
    def has_apify_api_token(self) -> bool:
        """Expose token presence without returning the secret."""
        from doormat.security.secrets import has_secret

        return has_secret(self.apify_api_token)

    @property
    def apify_token_last4(self) -> Optional[str]:
        """Expose a masked token hint for the UI."""
        from doormat.security.secrets import secret_last4

        return secret_last4(self.apify_api_token)


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
    # Scrape health tracking — set on every fetch attempt so we can skip dead domains.
    last_fetch_attempted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fetch_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    extraction_strategies: Mapped[list["ExtractionStrategy"]] = relationship(
        back_populates="property_manager"
    )
    listings: Mapped[list["Listing"]] = relationship(back_populates="property_manager")

    __table_args__ = (Index("idx_city_validated", "city", "validated"),)


class TrustedSource(Base):
    """User-curated listing sources (Craigslist region or property manager URL)."""

    __tablename__ = "trusted_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    linked_property_manager_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("property_managers.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("kind", "url", name="uq_trusted_source_kind_url"),)


class ExtractionStrategy(Base):
    """LLM-generated extraction strategies (scrapers)."""

    __tablename__ = "extraction_strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    property_manager_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("property_managers.id"), nullable=False, index=True
    )
    strategy_json: Mapped[str] = mapped_column(Text, nullable=False)  # LLM output
    api_recipe_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Serialized ApiRecipe
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
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="pm_direct")
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
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    saved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

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


class DiscoveryRun(Base):
    """Records each discovery run with status and timing."""

    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    preference_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    managers_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    logs: Mapped[list["DiscoveryRunLog"]] = relationship(
        back_populates="run", order_by="DiscoveryRunLog.sequence"
    )
    search_run: Mapped[Optional["SearchRun"]] = relationship(
        back_populates="discovery_run", uselist=False
    )

    __table_args__ = (Index("idx_run_city_started", "city", "started_at"),)


class SearchRun(Base):
    """Parent durable run wrapping discovery/scrape/filter/score for the UI."""

    __tablename__ = "search_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    discovery_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_runs.id"), nullable=False, unique=True, index=True
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    preference_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(64), default="discovery", nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    sources_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    managers_validated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    listings_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extraction_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    great_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    worth_a_look: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    near_misses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    filtered_out: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    cost_usd_so_far: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    active_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    filters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    discovery_run: Mapped["DiscoveryRun"] = relationship(back_populates="search_run")
    events: Mapped[list["SearchRunEvent"]] = relationship(
        back_populates="run", order_by="SearchRunEvent.sequence"
    )
    listing_results: Mapped[list["RunListingResult"]] = relationship(back_populates="run")

    __table_args__ = (Index("idx_search_run_status_started", "status", "started_at"),)


class SearchRunEvent(Base):
    """Typed, durable events for a search run."""

    __tablename__ = "search_run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_runs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="user", nullable=False)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True
    )

    run: Mapped["SearchRun"] = relationship(back_populates="events")

    __table_args__ = (Index("idx_search_run_event_run_seq", "run_id", "sequence"),)


class RunListingResult(Base):
    """Per-run, per-revision classification for a canonical listing."""

    __tablename__ = "run_listing_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("search_runs.id"), nullable=False)
    listing_id: Mapped[str] = mapped_column(String(36), ForeignKey("listings.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    filter_reasons_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    run: Mapped["SearchRun"] = relationship(back_populates="listing_results")
    listing: Mapped["Listing"] = relationship()

    __table_args__ = (
        UniqueConstraint("run_id", "listing_id", "revision", name="uq_run_listing_revision"),
        Index("idx_run_listing_result_run_rev", "run_id", "revision"),
        Index("idx_run_listing_result_run_cat", "run_id", "category"),
    )


class DiscoveryRunLog(Base):
    """Individual log lines for a discovery run."""

    __tablename__ = "discovery_run_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_runs.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # info|success|error|debug|warning
    component: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # discovery|extraction|scoring|agent
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON extra context

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    run: Mapped["DiscoveryRun"] = relationship(back_populates="logs")

    __table_args__ = (Index("idx_log_run_seq", "run_id", "sequence"),)


class GeocodeCache(Base):
    """Deduplicated Nominatim forward-geocode results (respect external rate limits)."""

    __tablename__ = "geocode_cache"

    cache_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=True
    )
