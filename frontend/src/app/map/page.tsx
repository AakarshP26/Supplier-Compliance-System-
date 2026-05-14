"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import dynamic from "next/dynamic";

// Leaflet must be imported client-side only (no SSR)
const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

interface MapSupplier {
  id: string;
  name: string;
  lat: number;
  lng: number;
  address: string | null;
  category: string;
  country: string;
  is_illustrative: boolean;
  score: number | null;
  grade: string | null;
  belief_safe: number | null;
  belief_risky: number | null;
  compliance_fails: number;
}

const GRADE_COLORS: Record<string, string> = {
  A: "#22c55e",
  B: "#86efac",
  C: "#fbbf24",
  D: "#f97316",
  F: "#ef4444",
};

export default function MapPage() {
  const [suppliers, setSuppliers] = useState<MapSupplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<MapSupplier | null>(null);
  const [filterGrade, setFilterGrade] = useState("all");
  const [filterCat, setFilterCat] = useState("all");
  const [filterType, setFilterType] = useState<"all" | "real" | "illustrative">("all");

  useEffect(() => {
    fetch("http://localhost:8000/api/suppliers/map")
      .then((r) => r.json())
      .then((d) => { setSuppliers(d); setLoading(false); })
      .catch(() => { setError("Backend unreachable"); setLoading(false); });
  }, []);

  const filtered = useMemo(() => {
    let rows = suppliers;
    if (filterGrade !== "all") rows = rows.filter((s) => s.grade === filterGrade);
    if (filterCat !== "all") rows = rows.filter((s) => s.category === filterCat);
    if (filterType === "real") rows = rows.filter((s) => !s.is_illustrative);
    if (filterType === "illustrative") rows = rows.filter((s) => s.is_illustrative);
    return rows;
  }, [suppliers, filterGrade, filterCat, filterType]);

  const cats = useMemo(() => [...new Set(suppliers.map((s) => s.category))].sort(), [suppliers]);

  const select = "bg-transparent border border-white/10 rounded px-2.5 py-1.5 text-[12px] text-white/60 focus:outline-none focus:border-white/25 hover:border-white/20 transition-colors appearance-none cursor-pointer";

  return (
    <div className="flex flex-col h-full bg-[#0A0A0A]">
      {/* Header bar */}
      <div className="shrink-0 border-b border-white/[0.07] px-6 py-4 flex items-center gap-6">
        <div>
          <p className="text-[10px] uppercase tracking-widest text-white/30 mb-0.5">Supplier Intelligence</p>
          <h1 className="text-lg font-semibold text-white/90 tracking-tight">Bengaluru Supplier Map</h1>
        </div>

        <div className="flex items-center gap-3 ml-auto">
          {loading && <span className="text-[11px] text-white/30 animate-pulse">Loading scores…</span>}

          <select value={filterGrade} onChange={(e) => setFilterGrade(e.target.value)} className={select}>
            <option value="all">All grades</option>
            {["A","B","C","D","F"].map((g) => <option key={g} value={g}>Grade {g}</option>)}
          </select>

          <select value={filterCat} onChange={(e) => setFilterCat(e.target.value)} className={select}>
            <option value="all">All categories</option>
            {cats.map((c) => <option key={c} value={c}>{c.replace(/_/g," ")}</option>)}
          </select>

          <select value={filterType} onChange={(e) => setFilterType(e.target.value as typeof filterType)} className={select}>
            <option value="all">Real + illustrative</option>
            <option value="real">Real only</option>
            <option value="illustrative">Illustrative only</option>
          </select>

          <span className="text-[11px] text-white/25 tabular-nums pl-2 border-l border-white/10">
            {loading ? "—" : `${filtered.length} pins`}
          </span>
        </div>
      </div>

      {/* Map + side panel */}
      <div className="flex flex-1 min-h-0">
        {/* Map */}
        <div className="flex-1 relative">
          {error && (
            <div className="absolute inset-0 flex items-center justify-center">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}
          {!error && (
            <MapView
              suppliers={filtered}
              gradeColors={GRADE_COLORS}
              onSelect={setSelected}
              selected={selected}
            />
          )}

          {/* Grade legend */}
          <div className="absolute bottom-6 left-4 z-[1000] bg-black/80 backdrop-blur border border-white/10 rounded-lg px-4 py-3 space-y-1.5">
            <p className="text-[9px] uppercase tracking-widest text-white/30 mb-2">Risk Grade</p>
            {Object.entries(GRADE_COLORS).map(([g, c]) => (
              <div key={g} className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c }} />
                <span className="text-[11px] text-white/60 font-mono">Grade {g}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 mt-1">
              <span className="w-2.5 h-2.5 rounded-full shrink-0 bg-white/20" />
              <span className="text-[11px] text-white/40 font-mono">Unscored</span>
            </div>
          </div>
        </div>

        {/* Side panel — supplier detail */}
        <div className={`shrink-0 border-l border-white/[0.07] bg-[#050505] transition-all duration-300 overflow-y-auto ${selected ? "w-80" : "w-0 overflow-hidden border-l-0"}`}>
          {selected && (
            <div className="p-5 space-y-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-white/30 mb-1">Selected Supplier</p>
                  <h2 className="text-base font-semibold text-white/90 leading-snug">{selected.name}</h2>
                  {selected.is_illustrative && (
                    <span className="text-[9px] uppercase tracking-widest text-white/30 border border-white/15 px-1 py-px rounded-sm mt-1 inline-block">sme</span>
                  )}
                </div>
                <button onClick={() => setSelected(null)} className="text-white/25 hover:text-white/60 text-lg leading-none shrink-0 mt-0.5">×</button>
              </div>

              {/* Score */}
              {selected.score != null && (
                <div className="border border-white/[0.07] rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[10px] uppercase tracking-widest text-white/30">DS Score</span>
                    <span className="text-lg font-semibold font-mono" style={{ color: GRADE_COLORS[selected.grade ?? ""] ?? "#fff" }}>
                      {selected.score.toFixed(1)}
                    </span>
                  </div>
                  <div className="w-full h-1 bg-white/[0.06] rounded-full overflow-hidden mb-3">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${selected.score}%`, background: GRADE_COLORS[selected.grade ?? ""] ?? "#fff" }}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono text-white/40">Grade</span>
                    <span className="text-[13px] font-bold font-mono" style={{ color: GRADE_COLORS[selected.grade ?? ""] ?? "#fff" }}>
                      {selected.grade}
                    </span>
                  </div>
                </div>
              )}

              {/* DS beliefs */}
              {selected.belief_safe != null && (
                <div className="space-y-2">
                  <p className="text-[10px] uppercase tracking-widest text-white/30">DS Belief Masses</p>
                  {[
                    { label: "m_safe", val: selected.belief_safe, color: "#22c55e" },
                    { label: "m_risky", val: selected.belief_risky ?? 0, color: "#ef4444" },
                    { label: "uncertainty", val: 1 - (selected.belief_safe + (selected.belief_risky ?? 0)), color: "#6366f1" },
                  ].map((b) => (
                    <div key={b.label} className="flex items-center gap-2">
                      <span className="text-[11px] font-mono text-white/40 w-20">{b.label}</span>
                      <div className="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.max(0, b.val) * 100}%`, background: b.color }} />
                      </div>
                      <span className="text-[11px] font-mono tabular-nums" style={{ color: b.color }}>{b.val.toFixed(3)}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Details */}
              <div className="space-y-2 text-[12px]">
                <Row label="Category" value={selected.category.replace(/_/g, " ")} />
                <Row label="Country" value={selected.country} mono />
                <Row label="Compliance" value={selected.compliance_fails === 0 ? "Pass" : `${selected.compliance_fails} fail(s)`} color={selected.compliance_fails === 0 ? "#22c55e" : "#ef4444"} />
                {selected.address && <Row label="Address" value={selected.address} />}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, mono, color }: { label: string; value: string; mono?: boolean; color?: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="text-white/30 w-24 shrink-0">{label}</span>
      <span className={`text-white/70 ${mono ? "font-mono" : ""} capitalize`} style={color ? { color } : undefined}>{value}</span>
    </div>
  );
}
