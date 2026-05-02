"""Unified scraping pipeline: PM direct + source adapters, with live run events."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

import httpx
import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from doormat.config import settings
from doormat.db.base import AsyncSessionLocal
from doormat.models.orm import Listing as ListingORM
from doormat.models.orm import Preference, PropertyManager, SearchRun, TrustedSource
from doormat.runs import events as run_events
from doormat.runs import filters as run_filters
from doormat.runs import state as run_state
from doormat.runs.errors import CooperativeCancel
from doormat.security.secrets import decrypt_secret
from doormat.sources.scrape_targets import fetch_property_manager_scrape_pages

logger = structlog.get_logger(__name__)


def _run_filter_snapshot(search_run: SearchRun, preference: Optional[Preference]) -> dict[str, Any]:
    """Load the run's frozen filter snapshot, falling back to preference defaults."""
    snapshot: dict[str, Any] = {}
    if search_run.filters_json:
        try:
            raw = json.loads(search_run.filters_json)
        except json.JSONDecodeError:
            raw = {}
        if isinstance(raw, dict):
            snapshot = raw
    if "sources_enabled" not in snapshot:
        snapshot["sources_enabled"] = run_filters.build_run_filter_snapshot(preference)[
            "sources_enabled"
        ]
    return snapshot


def _enabled_sources(search_run: SearchRun, preference: Optional[Preference]) -> list[str]:
    snapshot = _run_filter_snapshot(search_run, preference)
    sources = snapshot.get("sources_enabled")
    if isinstance(sources, list):
        cleaned = [source for source in sources if isinstance(source, str) and source.strip()]
        if cleaned:
            return cleaned
    if preference is None:
        return ["craigslist"]
    try:
        raw = preference.sources_enabled
        parsed = json.loads(raw) if raw else ["craigslist"]
        return [s for s in parsed if isinstance(s, str)]
    except (json.JSONDecodeError, AttributeError):
        return ["craigslist"]


def _scrapeable_property_managers_stmt(city: str):
    """Return the PM query used for PM-direct scraping."""
    return select(PropertyManager).where(
        PropertyManager.city == city,
        PropertyManager.validated == True,  # noqa: E712
        or_(PropertyManager.listing_page_url.isnot(None), PropertyManager.website.isnot(None)),
        PropertyManager.name.notin_(["Craigslist", "Zillow", "Facebook Marketplace"]),
    )


async def _get_or_create_source_pm(
    session: AsyncSession,
    city: str,
    source_name: str,
    source_key: str,
) -> PropertyManager:
    """Get or create a singleton PropertyManager representing a listing source."""
    stmt = select(PropertyManager).where(
        PropertyManager.city == city,
        PropertyManager.name == source_name,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    pm = PropertyManager(
        id=str(uuid.uuid4()),
        city=city,
        name=source_name,
        website=f"https://{source_key}.com",
        listing_page_url=None,
        validated=True,
        discovery_timestamp=datetime.now(UTC),
    )
    session.add(pm)
    await session.commit()
    return pm


async def _cancel_check(search_run_id: str) -> bool:
    async with AsyncSessionLocal() as s:
        sr = await s.get(SearchRun, search_run_id)
        if sr is None:
            return False
        return bool(sr.cancel_requested or sr.status == "cancel_requested")


async def run_scraping_stage(
    search_run_id: str,
    city: str,
    preference_id: Optional[str],
) -> None:
    """Run scraping for all enabled sources, emit events, classify listings.

    Called automatically after discovery succeeds. Runs PM direct scraping
    plus any additional source adapters enabled in the preference.
    """
    async with AsyncSessionLocal() as session:
        search_run = await session.get(SearchRun, search_run_id)
        if search_run is None:
            logger.error("scrape_stage_run_not_found", run_id=search_run_id)
            return

        preference = await session.get(Preference, preference_id) if preference_id else None
        sources = _enabled_sources(search_run, preference)
        emitter = run_events.SearchRunEventEmitter(session, search_run_id)

        search_run.current_stage = "scraping"
        session.add(search_run)
        await session.commit()

        await emitter.stage_started("scraping", f"Scraping listings for {city}")

        try:
            await _scrape_all_sources(
                session, search_run, search_run_id, city, preference, sources, emitter
            )

            # Scoring stage
            await _run_scoring_stage(session, search_run, city, preference, emitter)

            search_run = await session.get(SearchRun, search_run_id)
            if search_run and not search_run.cancel_requested:
                search_run.status = "success"
                search_run.current_stage = "done"
                search_run.finished_at = datetime.now(UTC)
                run_events.sync_run_cost_from_tracker(session, search_run)
                session.add(search_run)
                await session.commit()
                await emitter.stage_completed("done", "Run complete")

        except CooperativeCancel:
            search_run = await session.get(SearchRun, search_run_id)
            if search_run:
                await run_state.apply_cancelled_terminal_state(session, search_run, None)
            await emitter.emit("cancelled", "Run cancelled", stage="scraping")
        except Exception as exc:
            logger.error("scraping_stage_failed", error=str(exc), exc_info=True)
            search_run = await session.get(SearchRun, search_run_id)
            if search_run:
                search_run.status = "error"
                search_run.current_stage = "error"
                search_run.finished_at = datetime.now(UTC)
                session.add(search_run)
                await session.commit()
            await emitter.emit("error", f"Scraping failed: {exc}", stage="scraping")


async def _scrape_all_sources(
    session: AsyncSession,
    search_run: SearchRun,
    search_run_id: str,
    city: str,
    preference: Optional[Preference],
    sources: list[str],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    await _scrape_pm_direct(session, search_run, city, preference, emitter)

    if await _cancel_check(search_run_id):
        raise CooperativeCancel()

    if "craigslist" in sources:
        await _scrape_craigslist(session, search_run, city, preference, emitter)

    if await _cancel_check(search_run_id):
        raise CooperativeCancel()

    apify_token = _get_apify_token(preference)
    if "zillow" in sources:
        if apify_token:
            await _scrape_zillow(session, search_run, city, apify_token, preference, emitter)
        else:
            await emitter.emit(
                "stage_progress", "Zillow skipped — no Apify token configured", stage="scraping"
            )

    if await _cancel_check(search_run_id):
        raise CooperativeCancel()

    if "facebook" in sources:
        if apify_token:
            await _scrape_facebook(session, search_run, city, apify_token, preference, emitter)
        else:
            await emitter.emit(
                "stage_progress",
                "Facebook Marketplace skipped — no Apify token configured",
                stage="scraping",
            )


# ─── PM Direct ───────────────────────────────────────────────────────────────


def _listing_found_message(result: Any, pm_name: str) -> str:
    """Build a human-readable 'Found listing' message for the activity feed."""
    listing = result.listing
    parts: list[str] = []
    if listing.bedrooms:
        parts.append(f"{listing.bedrooms}BR")
    if listing.rent:
        parts.append(f"${listing.rent:,.0f}/mo")
    addr = listing.address or ""
    if addr and "Unknown" not in addr:
        parts.append(f"— {addr[:60]}")
    summary = " ".join(parts) if parts else "listing"
    return f"Found: {summary} ({pm_name})"


async def _scrape_pm_direct(  # noqa: C901
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    from doormat.extraction.orchestrator import extract_listing

    stmt = _scrapeable_property_managers_stmt(city)
    all_pms = list((await session.execute(stmt)).scalars().all())

    # Skip PMs that failed recently — avoids burning time on dead domains every run.
    now_utc = datetime.now(UTC)

    def _recently_failed(pm: PropertyManager) -> bool:
        if pm.last_fetch_error is None or pm.last_fetch_attempted_at is None:
            return False
        attempted = pm.last_fetch_attempted_at
        if attempted.tzinfo is None:
            from datetime import timezone
            attempted = attempted.replace(tzinfo=timezone.utc)
        return (now_utc - attempted).total_seconds() < 86400  # 24 hours

    skipped_pms = [pm for pm in all_pms if _recently_failed(pm)]
    pms = [pm for pm in all_pms if not _recently_failed(pm)]

    if skipped_pms:
        await emitter.emit(
            "stage_progress",
            f"Skipping {len(skipped_pms)} manager(s) that failed recently",
            stage="scraping",
            payload={"count": len(skipped_pms)},
            visibility="developer",
        )

    if not pms:
        await emitter.emit(
            "stage_progress",
            "No validated property managers with scrapeable URLs — skipping PM direct scraping",
            stage="scraping",
        )
        return

    await emitter.emit(
        "stage_progress",
        f"Scraping {len(pms)} property manager site(s)",
        stage="scraping",
        payload={"count": len(pms)},
    )

    listings_found = 0
    unreachable_count = 0
    for pm in pms:
        pm_validated = False
        await emitter.emit(
            "stage_progress",
            f"Checking {pm.name}…",
            stage="scraping",
            payload={"pm": pm.name, "url": pm.listing_page_url or pm.website},
        )
        # Shorter connect timeout so DNS failures fail fast (<5s) instead of waiting 20s
        _timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
        try:
            async with httpx.AsyncClient(timeout=_timeout, follow_redirects=True) as client:
                pages = await fetch_property_manager_scrape_pages(client, pm, max_candidate_links=8)
            # Success — clear any previous error
            pm.last_fetch_attempted_at = now_utc
            pm.last_fetch_error = None
            session.add(pm)
        except (httpx.HTTPError, Exception) as exc:
            # Demote to developer-only; summarise at end
            unreachable_count += 1
            pm.last_fetch_attempted_at = now_utc
            pm.last_fetch_error = str(exc)[:500]
            session.add(pm)
            await emitter.emit(
                "warning",
                f"Could not fetch {pm.name}: {exc}",
                stage="scraping",
                payload={"pm": pm.name, "error": str(exc)},
                visibility="developer",
            )
            search_run.sources_checked += 1
            session.add(search_run)
            await session.commit()
            continue

        search_run.sources_checked += 1
        session.add(search_run)
        await session.commit()

        if not pages:
            await emitter.emit(
                "warning",
                f"No scrape pages discovered for {pm.name}",
                stage="scraping",
                payload={"pm": pm.name},
            )
            continue

        await emitter.emit(
            "stage_progress",
            f"Discovered {len(pages)} scrape page(s) for {pm.name}",
            stage="scraping",
            payload={"pm": pm.name, "count": len(pages)},
        )

        for page_url, page_html in pages:
            try:
                # Brief visible "Scanning…" event before what could be a long LLM call
                short_path = page_url.split("?")[0][-60:]
                await emitter.emit(
                    "stage_progress",
                    f"Scanning {short_path}",
                    stage="scraping",
                    payload={"pm": pm.name, "url": page_url},
                )
                result = await extract_listing(session, page_html, page_url, pm, preference)
                if result.confidence != "low":
                    listings_found += 1
                    search_run = await session.get(SearchRun, search_run.id) or search_run
                    search_run.extraction_attempts += 1
                    search_run.listings_seen += 1
                    if not pm_validated:
                        search_run.managers_validated += 1
                        pm_validated = True
                    session.add(search_run)
                    await session.commit()

                    # Find the newly saved listing and classify it
                    if preference:
                        from sqlalchemy import select as sa_select

                        last = await session.execute(
                            sa_select(ListingORM)
                            .where(
                                ListingORM.property_manager_id == pm.id,
                                ListingORM.url == page_url,
                            )
                            .order_by(ListingORM.extraction_timestamp.desc())
                            .limit(1)
                        )
                        listing_row = last.scalar_one_or_none()
                        if listing_row:
                            await run_filters.persist_listing_classification(
                                session,
                                run=search_run,
                                listing=listing_row,
                                preference=preference,
                                emitter=emitter,
                            )
                            await session.commit()

                    await emitter.emit(
                        "listing_found",
                        _listing_found_message(result, pm.name),
                        stage="scraping",
                        payload={
                            "pm": pm.name,
                            "confidence": result.confidence,
                            "address": result.listing.address,
                            "price": result.listing.rent,
                            "bedrooms": result.listing.bedrooms,
                        },
                    )
                else:
                    search_run = await session.get(SearchRun, search_run.id) or search_run
                    search_run.extraction_attempts += 1
                    session.add(search_run)
                    await session.commit()
                    await emitter.emit(
                        "warning",
                        f"Low-confidence extraction from {pm.name} — skipped",
                        stage="scraping",
                        payload={"pm": pm.name, "reasoning": result.reasoning},
                    )
            except Exception as exc:
                logger.error("pm_direct_extract_failed", pm=pm.name, url=page_url, error=str(exc))
                sr = await session.get(SearchRun, search_run.id) or search_run
                sr.extraction_attempts += 1
                session.add(sr)
                await session.commit()
                await emitter.emit(
                    "warning",
                    f"Extraction failed for {pm.name}: {exc}",
                    stage="scraping",
                    payload={"pm": pm.name, "url": page_url, "error": str(exc)},
                )

    await emitter.emit(
        "stage_progress",
        f"PM direct: {listings_found} listing(s) extracted from {len(pms)} site(s)",
        stage="scraping",
        payload={"found": listings_found, "sites": len(pms)},
    )

    # One user-visible summary if any PMs were unreachable
    total_attempted = len(pms)
    total_skipped = len(skipped_pms)
    if unreachable_count > 0:
        await emitter.emit(
            "warning",
            (
                f"⚠ {unreachable_count} of {total_attempted} manager(s) unreachable"
                + (f" ({total_skipped} skipped — failed recently)" if total_skipped else "")
                + " — see Technical Details"
            ),
            stage="scraping",
            payload={"unreachable": unreachable_count, "total": total_attempted},
        )
    elif total_skipped > 0:
        await emitter.emit(
            "stage_progress",
            f"{total_skipped} manager(s) skipped (failed in the last 24 h)",
            stage="scraping",
            payload={"skipped": total_skipped},
        )


# ─── Craigslist ───────────────────────────────────────────────────────────────


def _craigslist_subdomain_from_trusted_url(url: str) -> Optional[str]:
    from urllib.parse import urlparse

    try:
        host = (urlparse(url.strip()).netloc or "").lower()
    except ValueError:
        return None
    if not host.endswith(".craigslist.org"):
        return None
    sub = host.split(".")[0]
    return sub or None


async def _scrape_craigslist(
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    from doormat.sources.craigslist import _city_to_subdomain, fetch_craigslist_listings

    await emitter.emit(
        "stage_progress", f"Fetching Craigslist listings for {city}", stage="scraping"
    )

    city_key = city.strip().lower()
    stmt = select(TrustedSource).where(
        TrustedSource.kind == "craigslist_region",
        or_(
            TrustedSource.city.is_(None),
            func.lower(TrustedSource.city) == city_key,
            func.lower(TrustedSource.city).like(city_key + ",%"),
            func.lower(TrustedSource.city).like(city_key + " %"),
        ),
    )
    trusted_rows = list((await session.execute(stmt)).scalars().all())
    regions: list[tuple[str, str]] = []
    for tr in trusted_rows:
        sub = _craigslist_subdomain_from_trusted_url(tr.url)
        if sub:
            regions.append((sub, tr.label))

    used_auto = False
    if not regions:
        guessed = _city_to_subdomain(city)
        guessed_url = f"https://{guessed}.craigslist.org"
        used_auto = True
        await emitter.emit(
            "warning",
            (
                f"Auto-routed Craigslist to `{guessed_url}` — if this is the wrong region, "
                "add a trusted Craigslist region under /sources."
            ),
            stage="scraping",
            payload={"subdomain": guessed, "city": city},
        )
        regions = [(guessed, "auto")]

    cl_pm = await _get_or_create_source_pm(session, city, "Craigslist", "craigslist")
    saved = 0
    seen_urls: set[str] = set()
    total_candidates = 0

    for sub, _src_label in regions:
        raw_listings = await fetch_craigslist_listings(city, max_results=40, subdomain=sub)
        total_candidates += len(raw_listings)
        if raw_listings:
            await emitter.emit(
                "stage_progress",
                f"Craigslist ({sub}): found {len(raw_listings)} candidates",
                stage="scraping",
                payload={"count": len(raw_listings), "subdomain": sub},
            )

        for raw in raw_listings:
            if raw.url in seen_urls:
                continue
            if not raw.price or raw.price < 100:
                continue

            existing = await session.execute(
                select(ListingORM).where(ListingORM.url == raw.url).limit(1)
            )
            if existing.scalar_one_or_none():
                seen_urls.add(raw.url)
                continue

            listing_id = str(uuid.uuid4())
            listing = ListingORM(
                id=listing_id,
                property_manager_id=cl_pm.id,
                preference_id=preference.id if preference else None,
                address=raw.address or raw.neighborhood or raw.title or city,
                bedrooms=raw.bedrooms,
                price=raw.price,
                url=raw.url,
                pets_policy="unknown",
                source="craigslist",
                extraction_timestamp=datetime.now(UTC),
                validation_passed=True,
            )
            session.add(listing)
            await session.commit()
            saved += 1
            seen_urls.add(raw.url)

            search_run = await session.get(SearchRun, search_run.id) or search_run
            search_run.extraction_attempts += 1
            search_run.listings_seen += 1
            session.add(search_run)
            await session.commit()

            if preference:
                await run_filters.persist_listing_classification(
                    session,
                    run=search_run,
                    listing=listing,
                    preference=preference,
                    emitter=emitter,
                )
                await session.commit()

    if total_candidates == 0:
        await emitter.emit(
            "warning", "No Craigslist listings found (page may have changed)", stage="scraping"
        )
        return

    await emitter.emit(
        "stage_progress",
        f"Craigslist: saved {saved} listing(s)"
        + (" (auto-routed — confirm region in /sources)" if used_auto else ""),
        stage="scraping",
        payload={"saved": saved, "auto_routed": used_auto},
    )


# ─── Zillow ───────────────────────────────────────────────────────────────────


async def _scrape_zillow(
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    apify_token: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    from doormat.sources.apify import fetch_zillow_listings

    await emitter.emit(
        "stage_progress", f"Fetching Zillow listings for {city} via Apify", stage="scraping"
    )

    raw_listings = await fetch_zillow_listings(city, apify_token, max_results=30)
    if not raw_listings:
        await emitter.emit("warning", "No Zillow listings returned", stage="scraping")
        return

    await _persist_apify_listings(
        session, search_run, city, preference, emitter, raw_listings, "zillow", "Zillow"
    )


# ─── Facebook ─────────────────────────────────────────────────────────────────


async def _scrape_facebook(
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    apify_token: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    from doormat.sources.apify import fetch_facebook_listings

    await emitter.emit(
        "stage_progress",
        f"Fetching Facebook Marketplace listings for {city} via Apify",
        stage="scraping",
    )

    raw_listings = await fetch_facebook_listings(city, apify_token, max_results=30)
    if not raw_listings:
        await emitter.emit("warning", "No Facebook Marketplace listings returned", stage="scraping")
        return

    await _persist_apify_listings(
        session,
        search_run,
        city,
        preference,
        emitter,
        raw_listings,
        "facebook",
        "Facebook Marketplace",
    )


async def _persist_apify_listings(
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
    raw_listings: list[Any],
    source_key: str,
    source_label: str,
) -> None:
    source_pm = await _get_or_create_source_pm(session, city, source_label, source_key)
    saved = 0

    for raw in raw_listings:
        if not raw.price or raw.price < 100:
            continue
        if not raw.url:
            continue

        existing = await session.execute(
            select(ListingORM).where(ListingORM.url == raw.url).limit(1)
        )
        if existing.scalar_one_or_none():
            continue

        listing = ListingORM(
            id=str(uuid.uuid4()),
            property_manager_id=source_pm.id,
            preference_id=preference.id if preference else None,
            address=raw.address or city,
            bedrooms=raw.bedrooms,
            bathrooms=raw.bathrooms,
            sqft=raw.sqft,
            price=raw.price,
            url=raw.url,
            pets_policy="unknown",
            description=raw.description,
            photos=json.dumps(raw.photos) if raw.photos else None,
            source=source_key,
            extraction_timestamp=datetime.now(UTC),
            validation_passed=True,
        )
        session.add(listing)
        await session.commit()
        saved += 1

        search_run = await session.get(SearchRun, search_run.id) or search_run
        search_run.extraction_attempts += 1
        search_run.listings_seen += 1
        session.add(search_run)
        await session.commit()

        if preference:
            await run_filters.persist_listing_classification(
                session,
                run=search_run,
                listing=listing,
                preference=preference,
                emitter=emitter,
            )
            await session.commit()

    await emitter.emit(
        "stage_progress",
        f"{source_label}: saved {saved} listing(s)",
        stage="scraping",
        payload={"saved": saved, "source": source_key},
    )


# ─── Scoring ──────────────────────────────────────────────────────────────────


async def _run_scoring_stage(
    session: AsyncSession,
    search_run: SearchRun,
    city: str,
    preference: Optional[Preference],
    emitter: run_events.SearchRunEventEmitter,
) -> None:
    if not preference:
        return

    from doormat.scoring.scorer import ListingScorer

    search_run = await session.get(SearchRun, search_run.id) or search_run
    search_run.current_stage = "scoring"
    session.add(search_run)
    await session.commit()

    await emitter.stage_started("scoring", "Scoring listings against your preferences")

    # Query ALL validated, unscored listings for this city (by PM city join), not just
    # those with a specific preference_id. PM-direct listings have preference_id=NULL
    # and would be silently skipped by a preference_id filter.
    stmt = (
        select(ListingORM)
        .join(PropertyManager, ListingORM.property_manager_id == PropertyManager.id)
        .where(
            PropertyManager.city == city,
            ListingORM.score.is_(None),
            ListingORM.validation_passed == True,  # noqa: E712
        )
        .limit(100)
    )
    unscored = list((await session.execute(stmt)).scalars().all())

    if unscored:
        scorer = ListingScorer()
        await scorer.score_batch(unscored, preference)
        await session.commit()
        # Emit per-listing scored events so the feed shows activity
        for listing in unscored:
            if listing.score is not None:
                score_pct = int(listing.score * 100) if listing.score <= 1 else int(listing.score)
                short_addr = (listing.address or "listing")[:50]
                await emitter.emit(
                    "listing_scored",
                    f"Scored: {short_addr} — {score_pct}/100",
                    stage="scoring",
                    payload={"address": listing.address, "score": listing.score},
                )
        await emitter.emit(
            "stage_progress",
            f"Scored {len(unscored)} listing(s)",
            stage="scoring",
            payload={"count": len(unscored)},
        )
    else:
        await emitter.emit("stage_progress", "No listings to score", stage="scoring")

    # Reclassify all city listings using the final LLM scores so that
    # great_matches / worth_a_look / near_misses / filtered_out are accurate.
    search_run = await session.get(SearchRun, search_run.id) or search_run
    classified = await run_filters.classify_city_listings_for_run(
        session,
        run=search_run,
        city=city,
        preference=preference,
        emitter=emitter,
    )
    await session.commit()
    await emitter.emit(
        "stage_progress",
        f"Classified {classified} listing(s)",
        stage="scoring",
        payload={"classified": classified},
    )

    await emitter.stage_completed("scoring", "Scoring complete")


def _get_apify_token(preference: Optional[Preference]) -> str:
    if preference and preference.apify_api_token:
        decrypted = decrypt_secret(preference.apify_api_token)
        if decrypted:
            return decrypted
    return settings.APIFY_API_TOKEN
