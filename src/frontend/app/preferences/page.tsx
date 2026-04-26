"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

interface Preference {
  id: string;
  description: string;
  city: string;
  created_at: string;
  updated_at: string;
}

async function fetchPreferences(): Promise<Preference[]> {
  const res = await fetch(`${API_BASE}/api/preferences`);
  if (!res.ok) return [];
  return res.json();
}

async function createPreference(description: string, city: string): Promise<Preference | null> {
  const res = await fetch(`${API_BASE}/api/preferences`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, city }),
  });
  if (!res.ok) return null;
  return res.json();
}

async function deletePreference(id: string): Promise<boolean> {
  const res = await fetch(`${API_BASE}/api/preferences/${id}`, { method: "DELETE" });
  return res.ok;
}

export default function PreferencesPage() {
  const [preferences, setPreferences] = useState<Preference[]>([]);
  const [description, setDescription] = useState("");
  const [city, setCity] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPreferences().then(setPreferences);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (description.length < 10) {
      setError("Description must be at least 10 characters.");
      return;
    }
    setSaving(true);
    const created = await createPreference(description, city);
    if (created) {
      setPreferences((prev) => [created, ...prev]);
      setDescription("");
      setCity("");
    } else {
      setError("Failed to save preference. Is the backend running?");
    }
    setSaving(false);
  };

  const handleDelete = async (id: string) => {
    const ok = await deletePreference(id);
    if (ok) setPreferences((prev) => prev.filter((p) => p.id !== id));
  };

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Search Preferences</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Describe what you&apos;re looking for in plain language. Doormat uses this to score listings.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New Preference</CardTitle>
          <CardDescription>
            Describe your ideal rental — budget, location, pets, amenities, vibe.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="city">City</Label>
              <Input
                id="city"
                placeholder="Austin, TX"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                required
                minLength={2}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="description">What are you looking for?</Label>
              <Textarea
                id="description"
                placeholder="2BR, pet-friendly (small dog), under $2,000/mo, walkable neighborhood, in-unit laundry preferred"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                required
                minLength={10}
                rows={4}
              />
              <p className="text-xs text-muted-foreground">{description.length}/1000 characters</p>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : "Save Preference"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {preferences.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
            Saved Preferences
          </h2>
          {preferences.map((pref) => (
            <Card key={pref.id}>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{pref.city}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {new Date(pref.created_at).toLocaleDateString()}
                      </span>
                    </div>
                    <p className="text-sm">{pref.description}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleDelete(pref.id)}
                  >
                    Delete
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
