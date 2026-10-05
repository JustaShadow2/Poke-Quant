import Link from "next/link";

export default function NotFound() {
  return (
    <div className="panel p-8 text-center">
      <p className="text-sm uppercase tracking-wide text-terminal-muted">404</p>
      <h1 className="mt-2 text-xl font-semibold text-white">Not found</h1>
      <p className="mt-1 text-sm text-terminal-muted">
        That instrument doesn&apos;t exist in the catalog.
      </p>
      <Link
        href="/"
        className="mt-4 inline-block rounded border border-terminal-border px-3 py-1.5 text-sm text-info hover:bg-white/5"
      >
        Back to catalog
      </Link>
    </div>
  );
}
