import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function Home() {
  return (
    <div className="space-y-10 max-w-3xl">
      <div className="space-y-3">
        <h1 className="text-4xl font-bold tracking-tight">🚪 Doormat</h1>
        <p className="text-xl text-muted-foreground">
          AI-powered rental finder. Discovers property managers, extracts listings,
          and scores them against your preferences — automatically.
        </p>
        <div className="flex gap-3 pt-2">
          <Link
            href="/listings"
            className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/80"
          >
            Browse Listings
          </Link>
          <Link
            href="/preferences"
            className="inline-flex items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            Set Preferences
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">🔍 Discovery</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Autonomous agents find property managers in your target city using browser automation and LLM search.
            </CardDescription>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">📄 Extraction</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              Two-tier extraction pipeline pulls price, bedrooms, pets policy, and amenities from listing pages.
            </CardDescription>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">⭐ Scoring</CardTitle>
          </CardHeader>
          <CardContent>
            <CardDescription>
              LLM scores each listing against your natural language preferences with explanations.
            </CardDescription>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
