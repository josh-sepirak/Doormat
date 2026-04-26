import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Doormat — AI Rental Finder",
  description: "Autonomous rental listing discovery and scoring",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <nav className="border-b px-6 py-3 flex items-center gap-6 bg-background">
          <Link href="/" className="font-semibold text-lg">Doormat</Link>
          <Link href="/listings" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Listings
          </Link>
          <Link href="/preferences" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            Preferences
          </Link>
        </nav>
        <main className="flex-1 container mx-auto px-6 py-8 max-w-6xl">
          <NuqsAdapter>{children}</NuqsAdapter>
        </main>
      </body>
    </html>
  );
}
