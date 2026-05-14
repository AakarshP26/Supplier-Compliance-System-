"use client";

import { useEffect, useState, useMemo } from "react";

interface Supplier {
  id: string;
  name: string;
  country: string;
  category: string;
  score: number;
  grade: string;
  belief_safe: number;
  belief_risky: number;
  uncertainty: number;
  compliance_fails: number;
  article_count: number;
  is_illustrative: boolean;
  error?: string;
}

type SortKey = "score" | "name" | "compliance_fails" | "article_count";

const GRADE_DOT: Record<string, string> = {
  A: "bg-[#22c55e]",
  B: "bg-[#86efac]",
  C: "bg-[#fbbf24]",
  D: "bg-[#f97316]",
  F: "bg-[#ef4444]",
};

const GRADE_TEXT: Record<string, string> = {
  A: "text-[#22c55e]",
  B: "text-[#86efac]",
  C: "text-[#fbbf24]",
  D: "text-[#f97316]",
  F: "text-[#ef4444]",
};

const SCORE_TRACK: Record<string, string> = {
  A: "bg-[#22c55e]/70",
  B: "bg-[#86efac]/70",
  C: "bg-[#fbbf24]/70",
  D: "bg-[#f97316]/70",
  F: "bg-[#ef4444]/70",
};

function StatPill({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-widest text-white/30 font-medium">{label}</span>
      <span className="text-xl font-semibold tabular-nums text-white/90">{value}</span>
      {sub && <span className="text-[11px] text-white/30">{sub}</span>}
    </div>
  );
}

function ColHeader({
  label, sortKey, active, asc, onSort,
}: {
  label: string; sortKey: SortKey; active: boolean; asc: boolean; onSort: (k: SortKey) => void;
}) {
  return (
    <th
      onClick={() => onSort(sortKey)}
      className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30 hover:text-white/60 cursor-pointer select-none whitespace-nowrap transition-colors"
    >
      {label}
      <span className={`ml-1 ${active ? "text-white/60" : "text-white/15"}`}>
        {active ? (asc ? "↑" : "↓") : "↕"}
      </span>
    </th>
  );
}

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState("");
  const [filterGrade, setFilterGrade] = useState("all");
  const [filterType, setFilterType] = useState<"all" | "real" | "illustrative">("all");
  const [filterComp, setFilterComp] = useState<"all" | "pass" | "fail">("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    fetch("http://localhost:8000/api/suppliers/scored")
      .then((r) => r.json())
      .then((data: Supplier[]) => {
        setSuppliers(data.filter((s) => !s.error));
        setLoading(false);
      })
      .catch(() => {
        setError("Backend unreachable — is the FastAPI server running on :8000?");
        setLoading(false);
      });
  }, []);

  const stats = useMemo(() => {
    if (!suppliers.length) return null;
    const risky = suppliers.filter((s) => s.score < 50).length;
    const compFail = suppliers.filter((s) => s.compliance_fails > 0).length;
    const avg = suppliers.reduce((a, s) => a + s.score, 0) / suppliers.length;
    return { risky, compFail, avg };
  }, [suppliers]);

  const filtered = useMemo(() => {
    let rows = [...suppliers];
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (s) => s.name.toLowerCase().includes(q) || s.country.toLowerCase().includes(q) || s.category.toLowerCase().includes(q)
      );
    }
    if (filterGrade !== "all") rows = rows.filter((s) => s.grade === filterGrade);
    if (filterType === "real") rows = rows.filter((s) => !s.is_illustrative);
    if (filterType === "illustrative") rows = rows.filter((s) => s.is_illustrative);
    if (filterComp === "pass") rows = rows.filter((s) => s.compliance_fails === 0);
    if (filterComp === "fail") rows = rows.filter((s) => s.compliance_fails > 0);

    rows.sort((a, b) => {
      const cmp =
        sortKey === "name" ? a.name.localeCompare(b.name) : (a[sortKey] as number) - (b[sortKey] as number);
      return sortAsc ? cmp : -cmp;
    });
    return rows;
  }, [suppliers, search, filterGrade, filterType, filterComp, sortKey, sortAsc]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortAsc((v) => !v);
    else { setSortKey(key); setSortAsc(key !== "score"); }
  }

  const select =
    "bg-transparent border border-white/10 rounded px-2.5 py-1.5 text-[12px] text-white/60 focus:outline-none focus:border-white/25 hover:border-white/20 transition-colors appearance-none cursor-pointer";

  return (
    <div className="h-full overflow-y-auto bg-[#0A0A0A]">
      <div className="max-w-[1400px] mx-auto px-8 py-8 space-y-8">

        {/* Page header */}
        <div className="border-b border-white/8 pb-6">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-[11px] uppercase tracking-widest text-white/30 mb-1">Risk Intelligence</p>
              <h1 className="text-2xl font-semibold text-white/90 tracking-tight">Supplier Registry</h1>
            </div>
            {stats && !loading && (
              <div className="flex items-end gap-10">
                <StatPill label="Total" value={suppliers.length} />
                <StatPill label="At risk" value={stats.risky} sub="score < 50" />
                <StatPill label="Compliance fails" value={stats.compFail} />
                <StatPill label="Avg score" value={stats.avg.toFixed(1)} />
              </div>
            )}
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-72">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-white/25" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search supplier, country, category…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-transparent border border-white/10 rounded text-[12px] text-white/80 placeholder-white/25 focus:outline-none focus:border-white/25 transition-colors"
            />
          </div>

          <select value={filterGrade} onChange={(e) => setFilterGrade(e.target.value)} className={select}>
            <option value="all">All grades</option>
            {["A", "B", "C", "D", "F"].map((g) => <option key={g} value={g}>Grade {g}</option>)}
          </select>

          <select value={filterComp} onChange={(e) => setFilterComp(e.target.value as typeof filterComp)} className={select}>
            <option value="all">All compliance</option>
            <option value="pass">Pass</option>
            <option value="fail">Fail</option>
          </select>

          <select value={filterType} onChange={(e) => setFilterType(e.target.value as typeof filterType)} className={select}>
            <option value="all">Real + illustrative</option>
            <option value="real">Real only</option>
            <option value="illustrative">Illustrative only</option>
          </select>

          <span className="text-[11px] text-white/25 ml-auto tabular-nums">
            {loading ? "—" : `${filtered.length} / ${suppliers.length}`}
          </span>
        </div>

        {/* Loading */}
        {loading && (
          <div className="flex items-center gap-3 py-16">
            <div className="w-4 h-4 border border-white/30 border-t-white/80 rounded-full animate-spin" />
            <span className="text-[12px] text-white/40 tracking-wide">Computing DS-fusion scores for all suppliers…</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="py-8 text-[12px] text-red-400/80">{error}</div>
        )}

        {/* Table */}
        {!loading && !error && (
          <div className="border border-white/[0.07] rounded-sm overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-white/[0.025] border-b border-white/[0.07]">
                  <th className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30 w-8">#</th>
                  <ColHeader label="Supplier" sortKey="name" active={sortKey === "name"} asc={sortAsc} onSort={toggleSort} />
                  <th className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30">Country</th>
                  <th className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30">Category</th>
                  <th className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30">Grade</th>
                  <ColHeader label="Score" sortKey="score" active={sortKey === "score"} asc={sortAsc} onSort={toggleSort} />
                  <th className="px-4 py-2.5 text-left text-[11px] uppercase tracking-widest font-medium text-white/30">DS Masses</th>
                  <ColHeader label="Compliance" sortKey="compliance_fails" active={sortKey === "compliance_fails"} asc={sortAsc} onSort={toggleSort} />
                  <ColHeader label="Articles" sortKey="article_count" active={sortKey === "article_count"} asc={sortAsc} onSort={toggleSort} />
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-[12px] text-white/20 tracking-wide">
                      No suppliers match the current filters.
                    </td>
                  </tr>
                )}
                {filtered.map((s, i) => (
                  <tr
                    key={s.id}
                    className="border-b border-white/[0.05] hover:bg-white/[0.025] transition-colors group"
                  >
                    {/* Index */}
                    <td className="px-4 py-3 text-[11px] text-white/20 tabular-nums">{i + 1}</td>

                    {/* Name */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${GRADE_DOT[s.grade] ?? "bg-white/20"}`} />
                        <span className="text-[13px] text-white/85 font-medium tracking-tight">{s.name}</span>
                        {s.is_illustrative && (
                          <span className="text-[9px] uppercase tracking-widest text-white/25 border border-white/10 px-1 py-px rounded-sm">
                            sme
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Country */}
                    <td className="px-4 py-3 text-[12px] text-white/45 font-mono tracking-widest">{s.country}</td>

                    {/* Category */}
                    <td className="px-4 py-3 text-[12px] text-white/45 capitalize">{s.category.replace(/_/g, " ")}</td>

                    {/* Grade */}
                    <td className="px-4 py-3">
                      <span className={`text-[13px] font-semibold font-mono ${GRADE_TEXT[s.grade] ?? "text-white/40"}`}>
                        {s.grade}
                      </span>
                    </td>

                    {/* Score */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div className="w-16 h-[3px] bg-white/[0.06] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${SCORE_TRACK[s.grade] ?? "bg-white/20"}`}
                            style={{ width: `${s.score}%` }}
                          />
                        </div>
                        <span className="text-[12px] font-mono text-white/70 tabular-nums w-10">{s.score.toFixed(1)}</span>
                      </div>
                    </td>

                    {/* DS Masses */}
                    <td className="px-4 py-3">
                      <span className="text-[11px] font-mono text-white/35 tabular-nums">
                        <span className="text-[#22c55e]/70">{s.belief_safe.toFixed(2)}</span>
                        <span className="text-white/15 mx-0.5">·</span>
                        <span className="text-[#ef4444]/70">{s.belief_risky.toFixed(2)}</span>
                        <span className="text-white/15 mx-0.5">·</span>
                        <span>{s.uncertainty.toFixed(2)}</span>
                      </span>
                    </td>

                    {/* Compliance */}
                    <td className="px-4 py-3 text-[12px] font-mono">
                      {s.compliance_fails === 0 ? (
                        <span className="text-white/30">—</span>
                      ) : (
                        <span className="text-[#ef4444]/80">{s.compliance_fails} fail{s.compliance_fails > 1 ? "s" : ""}</span>
                      )}
                    </td>

                    {/* Articles */}
                    <td className="px-4 py-3 text-[12px] font-mono text-white/30 tabular-nums">{s.article_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
