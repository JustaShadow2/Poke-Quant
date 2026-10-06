"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Catalog" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/scanner", label: "Scanner" },
  { href: "/market", label: "Market" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/watchlist", label: "Watchlist" },
  { href: "/alerts", label: "Alerts" },
  { href: "/simulate", label: "Simulate" },
  { href: "/compare", label: "Compare" },
  { href: "/grade", label: "Grade" },
  { href: "/admin", label: "Admin" },
] as const;

export function NavLinks() {
  const path = usePathname();
  return (
    <nav className="ml-auto flex items-center gap-4 text-sm text-terminal-muted">
      {LINKS.map((link) => {
        const active =
          link.href === "/"
            ? path === "/"
            : path === link.href || path.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={
              active
                ? "text-white"
                : "transition-colors hover:text-white"
            }
          >
            {link.label}
          </Link>
        );
      })}
      <span className="badge border-terminal-border bg-terminal-panel text-terminal-muted">
        Phase 3
      </span>
    </nav>
  );
}
