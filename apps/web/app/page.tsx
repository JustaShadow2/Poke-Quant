import Link from "next/link";

import { listInstruments } from "@/lib/api";
import { formatDate, formatUSD } from "@/lib/format";

export const dynamic = "force-dynamic";

function ApiDownNotice() {
  return (
    <div className="panel p-6 text-sm">
      <p className="font-medium text-caution">API unavailable</p>
      <p className="mt-1 text-terminal-muted">
        Could not reach the PokéQuant API. Start the backend (see the README) and
        make sure <code className="text-slate-300">API_BASE_URL</code> points to
        it.
      </p>
    </div>
  );
}

function EmptyCatalog() {
  return (
    <div className="panel p-6 text-sm">
      <p className="font-medium text-slate-200">No instruments yet</p>
      <p className="mt-1 text-terminal-muted">
        Seed the catalog and generate history:{" "}
        <code className="text-slate-300">
          pokequant seed && pokequant synth && pokequant ingest snapshot
        </code>
        .
      </p>
    </div>
  );
}

export default async function CatalogPage() {
  const data = await listInstruments({ limit: 100 });

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight text-white">
          Catalog
        </h1>
        <p className="mt-1 text-sm text-terminal-muted">
          Instruments tracked by the platform. Pokémon sealed products are the
          first asset class.
        </p>
      </section>

      {data === null ? (
        <ApiDownNotice />
      ) : data.items.length === 0 ? (
        <EmptyCatalog />
      ) : (
        <div className="panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-terminal-border px-4 py-2 text-xs text-terminal-muted">
            <span>
              {data.total} instrument{data.total === 1 ? "" : "s"}
            </span>
            <span className="uppercase tracking-wide">asset class · pokemon</span>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-terminal-border text-left text-xs uppercase tracking-wide text-terminal-muted">
                <th className="px-4 py-2 font-medium">Symbol</th>
                <th className="px-4 py-2 font-medium">Name</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Released</th>
                <th className="px-4 py-2 text-right font-medium">MSRP</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr
                  key={it.id}
                  className="group border-b border-terminal-border/60 transition-colors last:border-0 hover:bg-white/[0.03]"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/instruments/${it.id}`}
                      className="font-mono text-info transition-colors group-hover:text-white"
                    >
                      {it.symbol}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-slate-200">
                    <Link href={`/instruments/${it.id}`} className="hover:underline">
                      {it.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 text-terminal-muted">
                    {it.category ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 tnum text-terminal-muted">
                    {formatDate(it.release_date)}
                  </td>
                  <td className="px-4 py-2.5 tnum text-right text-slate-300">
                    {formatUSD(it.msrp_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
