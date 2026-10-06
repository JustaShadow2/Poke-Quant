import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import { AssistantDock } from "@/components/AssistantDock";
import { NavLinks } from "@/components/NavLinks";
import "./globals.css";

export const metadata: Metadata = {
  title: "PokéQuant — quantitative research for alternative assets",
  description:
    "A financial terminal for alternative assets. Forecasts, and risk — explained. Research, not investment advice.",
};

function TopBar() {
  return (
    <header className="sticky top-0 z-20 border-b border-terminal-border bg-terminal-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-lg font-semibold tracking-tight text-white">
            Poké<span className="text-info">Quant</span>
          </span>
          <span className="hidden text-xs text-terminal-muted sm:inline">
            alternative-assets research terminal
          </span>
        </Link>
        <NavLinks />
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-terminal-border">
      <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-terminal-muted">
        Research, not investment advice. Forecasts are model estimates with
        uncertainty and may be derived from calibrated synthetic data.
      </div>
    </footer>
  );
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="flex min-h-full flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
        <Footer />
        <AssistantDock />
      </body>
    </html>
  );
}
