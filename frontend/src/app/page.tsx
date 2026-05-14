"use client";

import { useState, useRef, useEffect } from "react";
import { BlurFade } from "@/components/ui/blur-fade";
import { ShieldCheck, ArrowUp, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  PieChart, Pie, Cell, Legend, ResponsiveContainer,
} from "recharts";

// ─── Chart spec types ───────────────────────────────────────────────────────

interface BarSpec {
  type: "bar";
  title: string;
  xKey: string;
  bars: { key: string; color: string; label?: string }[];
  data: Record<string, string | number>[];
  yLabel?: string;
  layout?: "horizontal" | "vertical";
}

interface DonutSpec {
  type: "donut";
  title: string;
  data: { name: string; value: number; color: string }[];
}

type ChartSpec = BarSpec | DonutSpec;

// ─── Chart components ────────────────────────────────────────────────────────

function ChartTooltipStyle({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#111] border border-white/10 rounded px-3 py-2 text-[11px] font-mono space-y-1">
      {label && <p className="text-white/50 mb-1">{label}</p>}
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>{p.name}: <span className="text-white/80">{typeof p.value === "number" ? p.value.toFixed(p.value % 1 === 0 ? 0 : 2) : p.value}</span></p>
      ))}
    </div>
  );
}

function BarChartCard({ spec }: { spec: BarSpec }) {
  const isVertical = spec.layout === "vertical";
  return (
    <div className="my-4 bg-white/[0.03] border border-white/[0.08] rounded-lg p-4">
      <p className="text-[11px] uppercase tracking-widest text-white/35 mb-4">{spec.title}</p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart
          data={spec.data}
          layout={isVertical ? "vertical" : "horizontal"}
          margin={{ top: 4, right: 16, bottom: 8, left: isVertical ? 140 : 0 }}
          barCategoryGap="30%"
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          {isVertical ? (
            <>
              <XAxis type="number" tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis dataKey={spec.xKey} type="category" tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} width={136} />
            </>
          ) : (
            <>
              <XAxis dataKey={spec.xKey} tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 10 }} axisLine={false} tickLine={false} label={spec.yLabel ? { value: spec.yLabel, angle: -90, position: "insideLeft", fill: "rgba(255,255,255,0.25)", fontSize: 10 } : undefined} />
            </>
          )}
          <Tooltip content={<ChartTooltipStyle />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
          {spec.bars.length > 1 && <Legend wrapperStyle={{ fontSize: 10, color: "rgba(255,255,255,0.4)" }} />}
          {spec.bars.map((b) => (
            <Bar key={b.key} dataKey={b.key} name={b.label ?? b.key} fill={b.color} radius={[2, 2, 0, 0]} maxBarSize={40} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

const RADIAN = Math.PI / 180;
function DonutLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }: { cx: number; cy: number; midAngle: number; innerRadius: number; outerRadius: number; percent: number }) {
  if (percent < 0.04) return null;
  const r = innerRadius + (outerRadius - innerRadius) * 0.55;
  const x = cx + r * Math.cos(-midAngle * RADIAN);
  const y = cy + r * Math.sin(-midAngle * RADIAN);
  return (
    <text x={x} y={y} fill="rgba(255,255,255,0.75)" textAnchor="middle" dominantBaseline="central" fontSize={11} fontFamily="monospace">
      {`${(percent * 100).toFixed(0)}%`}
    </text>
  );
}

function DonutChartCard({ spec }: { spec: DonutSpec }) {
  return (
    <div className="my-4 bg-white/[0.03] border border-white/[0.08] rounded-lg p-4">
      <p className="text-[11px] uppercase tracking-widest text-white/35 mb-4">{spec.title}</p>
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={spec.data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={95}
            paddingAngle={2}
            dataKey="value"
            labelLine={false}
            label={DonutLabel as Parameters<typeof Pie>[0]["label"]}
          >
            {spec.data.map((entry, i) => (
              <Cell key={i} fill={entry.color} stroke="transparent" />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltipStyle />} />
          <Legend
            wrapperStyle={{ fontSize: 10, color: "rgba(255,255,255,0.4)", paddingTop: 8 }}
            formatter={(value, entry) => (
              <span style={{ color: "rgba(255,255,255,0.55)" }}>
                {value} <span style={{ color: (entry as { color?: string }).color ?? "white" }}>({(entry as { payload?: { value: number } }).payload?.value ?? ""})</span>
              </span>
            )}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartBlock({ raw }: { raw: string }) {
  try {
    const spec: ChartSpec = JSON.parse(raw);
    if (spec.type === "bar") return <BarChartCard spec={spec} />;
    if (spec.type === "donut") return <DonutChartCard spec={spec} />;
  } catch {
    // fall through to raw display
  }
  return <pre className="text-[11px] text-white/30 bg-white/5 rounded p-3 overflow-auto">{raw}</pre>;
}

// ─── Markdown renderer with chart injection ───────────────────────────────────

function AssistantContent({ content }: { content: string }) {
  const parts: { type: "md" | "chart"; text: string }[] = [];
  const chartRe = /```chart\n([\s\S]*?)```/g;
  let last = 0;
  let m: RegExpExecArray | null;

  while ((m = chartRe.exec(content)) !== null) {
    if (m.index > last) parts.push({ type: "md", text: content.slice(last, m.index) });
    parts.push({ type: "chart", text: m[1].trim() });
    last = m.index + m[0].length;
  }
  if (last < content.length) parts.push({ type: "md", text: content.slice(last) });

  return (
    <div className="space-y-1">
      {parts.map((p, i) =>
        p.type === "chart" ? (
          <ChartBlock key={i} raw={p.text} />
        ) : (
          <div key={i} className="prose prose-sm prose-invert max-w-none text-white/75
            prose-p:leading-relaxed prose-p:my-1.5
            prose-strong:text-white/90 prose-strong:font-semibold
            prose-headings:text-white/90 prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-1
            prose-ul:my-1.5 prose-ul:space-y-0.5 prose-li:my-0
            prose-ol:my-1.5 prose-ol:space-y-0.5
            prose-code:text-indigo-300 prose-code:bg-indigo-500/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-code:before:content-none prose-code:after:content-none
            prose-hr:border-white/10 prose-hr:my-3
          ">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code(props) {
                  const { className, children } = props;
                  const lang = /language-(\w+)/.exec(className || "")?.[1];
                  if (lang === "chart") {
                    return <ChartBlock raw={String(children).trim()} />;
                  }
                  return <code className={className}>{children}</code>;
                },
              }}
            >
              {p.text}
            </ReactMarkdown>
          </div>
        )
      )}
    </div>
  );
}

// ─── Suggestions ──────────────────────────────────────────────────────────────

const SUGGESTIONS = [
  "Show score distribution chart",
  "Grade breakdown across portfolio",
  "Compare Dixon Electronics and BEL",
  "Which suppliers failed compliance checks?",
  "Show DS belief masses for Bosch India",
  "Run a red-team attack simulation",
];

type Message = { role: "user" | "assistant"; content: string };

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const hasMessages = messages.length > 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;
    setInput("");
    const newHistory = [...messages, { role: "user" as const, content: trimmed }];
    setMessages(newHistory);
    setLoading(true);
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const res = await fetch("http://localhost:8000/api/agent/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed, history: messages, context: { page: "Overview" } }),
      });

      if (!res.ok || !res.body) throw new Error("Stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6);
          if (payload === "[DONE]") break;
          try {
            const { token } = JSON.parse(payload);
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content: updated[updated.length - 1].content + token,
              };
              return updated;
            });
          } catch {}
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = { role: "assistant", content: "Error connecting to backend." };
        return updated;
      });
    }
    setLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="relative flex flex-col h-full">
      {hasMessages ? (
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-2xl mx-auto space-y-8">
            {messages.map((m, i) => (
              <div key={i}>
                {m.role === "user" ? (
                  <p className="text-2xl font-semibold text-white/90 leading-snug tracking-tight">{m.content}</p>
                ) : (
                  <div className="flex gap-3 mt-1">
                    <div className="mt-1 shrink-0 w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                      <ShieldCheck size={13} className="text-indigo-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <AssistantContent content={m.content} />
                    </div>
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="flex gap-3">
                <div className="mt-1 shrink-0 w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                  <ShieldCheck size={13} className="text-indigo-400" />
                </div>
                <div className="flex items-center gap-1.5 pt-1">
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-.15s]" />
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-.3s]" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center px-4 pb-40">
          <BlurFade delay={0.05}>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                <ShieldCheck size={20} className="text-indigo-400" />
              </div>
              <span className="text-white/30 text-sm font-medium tracking-widest uppercase">Compliance AI</span>
            </div>
          </BlurFade>

          <BlurFade delay={0.1}>
            <h1 className="text-4xl sm:text-5xl font-semibold text-center bg-gradient-to-br from-white to-white/40 bg-clip-text text-transparent leading-tight mb-4">
              What do you want to verify?
            </h1>
          </BlurFade>

          <BlurFade delay={0.15}>
            <p className="text-white/35 text-center text-base mb-10">
              Ask anything about your supplier network — compliance, risk scores, news intelligence.
            </p>
          </BlurFade>

          <BlurFade delay={0.2}>
            <div className="flex flex-wrap justify-center gap-2 max-w-xl">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-xs px-4 py-2 rounded-full border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] text-white/50 hover:text-white/80 transition-all duration-200"
                >
                  {s}
                </button>
              ))}
            </div>
          </BlurFade>
        </div>
      )}

      <div className="sticky bottom-0 px-4 pb-6 pt-4 bg-gradient-to-t from-[#0A0A0A] via-[#0A0A0A]/90 to-transparent">
        <div className="max-w-2xl mx-auto">
          {hasMessages && (
            <button
              onClick={() => setMessages([])}
              className="flex items-center gap-1.5 text-xs text-white/25 hover:text-white/50 transition mb-3 mx-auto"
            >
              <RotateCcw size={11} /> New conversation
            </button>
          )}
          <div className="relative group">
            <div className="absolute -inset-px rounded-2xl bg-gradient-to-r from-indigo-500/30 to-purple-500/30 opacity-0 group-focus-within:opacity-100 transition duration-300 blur-sm" />
            <div className="relative flex items-end gap-3 bg-white/[0.04] border border-white/10 rounded-2xl px-5 py-4 group-focus-within:border-white/20 transition-colors">
              <textarea
                ref={inputRef}
                rows={1}
                value={input}
                onChange={(e) => {
                  setInput(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px";
                }}
                onKeyDown={handleKeyDown}
                placeholder="Ask about a supplier, run a check, or simulate an attack…"
                className="flex-1 bg-transparent resize-none text-sm text-white placeholder:text-white/25 focus:outline-none leading-relaxed max-h-40 overflow-y-auto"
              />
              <button
                onClick={() => send(input)}
                disabled={loading || !input.trim()}
                className="shrink-0 w-8 h-8 rounded-xl bg-indigo-500 hover:bg-indigo-400 disabled:bg-white/5 disabled:text-white/20 flex items-center justify-center text-white transition-all duration-200 self-end"
              >
                <ArrowUp size={15} />
              </button>
            </div>
          </div>
          <p className="text-center text-[11px] text-white/15 mt-3">
            Powered by DeepSeek via OpenRouter · DS Fusion scoring · 85 suppliers indexed
          </p>
        </div>
      </div>
    </div>
  );
}
