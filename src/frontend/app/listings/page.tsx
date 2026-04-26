"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useQueryState, parseAsFloat, parseAsInteger, parseAsBoolean } from "nuqs";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

interface Listing {
  id: string;
  address: string;
  bedrooms: number | null;
  bathrooms: number | null;
  sqft: number | null;
  price: number;
  url: string;
  pets_policy: string;
  amenities: string[];
  description: string | null;
  score: number | null;
  score_explanation: string | null;
  saved: boolean;
  validation_passed: boolean;
  extraction_timestamp: string;
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null;
  const pct = Math.round(score * 100);
  const variant = score >= 0.75 ? "default" : score >= 0.5 ? "secondary" : "outline";
  return <Badge variant={variant}>{pct}% match</Badge>;
}

function ListingCard({ listing, onToggleSave }: { listing: Listing; onToggleSave: (id: string) => void }) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-1 flex-1 min-w-0">
            <p className="font-medium truncate">{listing.address}</p>
            <div className="flex flex-wrap gap-1.5 items-center">
              <span className="text-lg font-bold">${listing.price.toLocaleString()}/mo</span>
              {listing.bedrooms !== null && (
                <Badge variant="outline" className="text-xs">{listing.bedrooms}BR</Badge>
              )}
              {listing.bathrooms !== null && (
                <Badge variant="outline" className="text-xs">{listing.bathrooms}BA</Badge>
              )}
              {listing.sqft !== null && (
                <Badge variant="outline" className="text-xs">{listing.sqft.toLocaleString()} sqft</Badge>
              )}
              <ScoreBadge score={listing.score} />
            </div>
          </div>
          <Button
            variant={listing.saved ? "default" : "outline"}
            size="sm"
            onClick={() => onToggleSave(listing.id)}
            className="shrink-0"
          >
            {listing.saved ? "Saved" : "Save"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {listing.score_explanation && (
          <p className="text-xs text-muted-foreground italic">{listing.score_explanation}</p>
        )}
        {listing.description && (
          <p className="text-sm text-muted-foreground line-clamp-2">{listing.description}</p>
        )}
        {listing.amenities.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {listing.amenities.slice(0, 5).map((a) => (
              <Badge key={a} variant="secondary" className="text-xs">{a}</Badge>
            ))}
          </div>
        )}
        <div className="flex items-center justify-between pt-1">
          <span className="text-xs text-muted-foreground capitalize">
            Pets: {listing.pets_policy.replace(/_/g, " ")}
          </span>
          <a
            href={listing.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-primary hover:underline"
          >
            View listing →
          </a>
        </div>
      </CardContent>
    </Card>
  );
}

function ListingsContent() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // URL-state filters via nuqs
  const [maxPrice, setMaxPrice] = useQueryState("max_price", parseAsFloat);
  const [minBeds, setMinBeds] = useQueryState("min_bedrooms", parseAsInteger);
  const [savedOnly, setSavedOnly] = useQueryState("saved_only", parseAsBoolean.withDefault(false));
  const [minScore, setMinScore] = useQueryState("min_score", parseAsFloat);

  const fetchListings = useCallback(async (signal?: AbortSignal) => {
    const params = new URLSearchParams();
    if (maxPrice !== null) params.set("max_price", String(maxPrice));
    if (minBeds !== null) params.set("min_bedrooms", String(minBeds));
    if (savedOnly) params.set("saved_only", "true");
    if (minScore !== null) params.set("min_score", String(minScore));

    try {
      const res = await fetch(`${API_BASE}/api/listings?${params}`, { signal });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      setListings(await res.json());
      setError(null);
    } catch {
      if (signal?.aborted) return;
      setError("Could not load listings. Start the backend and try again.");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [maxPrice, minBeds, savedOnly, minScore]);

  useEffect(() => {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      void fetchListings(controller.signal);
    }, 0);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [fetchListings]);

  // SSE for real-time updates
  useEffect(() => {
    const es = new EventSource(`${API_BASE}/api/listings/stream`);
    es.onmessage = (ev) => {
      try {
        const newListing: Listing = JSON.parse(ev.data);
        setListings((prev) => {
          if (prev.find((l) => l.id === newListing.id)) return prev;
          return [newListing, ...prev];
        });
      } catch {
        setError("A live listing update could not be read.");
      }
    };
    return () => es.close();
  }, []);

  const handleToggleSave = async (id: string) => {
    const previous = listings;
    setListings((prev) =>
      prev.map((listing) => (listing.id === id ? { ...listing, saved: !listing.saved } : listing)),
    );

    try {
      const res = await fetch(`${API_BASE}/api/listings/${id}/save`, { method: "POST" });
      if (!res.ok) throw new Error(`Backend returned ${res.status}`);
      const updated: Listing = await res.json();
      setListings((prev) => prev.map((l) => (l.id === id ? updated : l)));
      setError(null);
    } catch {
      setListings(previous);
      setError("Could not update saved state.");
    }
  };

  const savedCount = listings.filter((l) => l.saved).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Listings</h1>
          <p className="text-muted-foreground text-sm mt-0.5">
            {listings.length} listing{listings.length !== 1 ? "s" : ""}
            {savedCount > 0 && ` · ${savedCount} saved`}
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 pb-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="space-y-1">
              <Label className="text-xs">Max price/mo</Label>
              <Input
                type="number"
                placeholder="$3,000"
                value={maxPrice ?? ""}
                onChange={(e) => setMaxPrice(e.target.value ? Number(e.target.value) : null)}
                className="w-32"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Min bedrooms</Label>
              <Input
                type="number"
                placeholder="1"
                value={minBeds ?? ""}
                onChange={(e) => setMinBeds(e.target.value ? Number(e.target.value) : null)}
                className="w-24"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Min score</Label>
              <Input
                type="number"
                placeholder="0.5"
                min="0"
                max="1"
                step="0.05"
                value={minScore ?? ""}
                onChange={(e) => setMinScore(e.target.value ? Number(e.target.value) : null)}
                className="w-24"
              />
            </div>
            <Button
              variant={savedOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setSavedOnly(!savedOnly)}
            >
              {savedOnly ? "Saved only" : "Show saved only"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setMaxPrice(null);
                setMinBeds(null);
                setSavedOnly(false);
                setMinScore(null);
              }}
            >
              Clear filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="h-40 pt-4" />
            </Card>
          ))}
        </div>
      ) : listings.length === 0 ? (
        <div className="rounded-2xl border border-dashed bg-card px-6 py-14 text-center text-muted-foreground">
          <p className="text-lg font-medium text-foreground">No matching listings yet</p>
          <p className="text-sm mt-1">Adjust filters, save a preference, or run discovery for a target city.</p>
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
          {listings.map((listing) => (
            <ListingCard key={listing.id} listing={listing} onToggleSave={handleToggleSave} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ListingsPage() {
  return (
    <Suspense fallback={<div className="py-16 text-center text-muted-foreground">Loading…</div>}>
      <ListingsContent />
    </Suspense>
  );
}
