"use client";

import { useState, useRef, useEffect } from "react";
import { BlurFade } from "@/components/ui/blur-fade";
import { ShieldCheck, ArrowUp, RotateCcw } from "lucide-react";

const SUGGESTIONS = [
  "Analyze top risky suppliers",
  "Which suppliers failed compliance checks?",
  "Run a red-team attack simulation",
  "Show news intelligence summary",
  "Find suppliers below score 40",
  "Explain how DS fusion scoring works",
];

type Message = { role: "user" | "assistant"; content: string };

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

    // Add an empty assistant message we'll stream into
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
      {/* Messages area */}
      {hasMessages ? (
        <div className="flex-1 overflow-y-auto px-4 py-8">
          <div className="max-w-2xl mx-auto space-y-8">
            {messages.map((m, i) => (
              <div key={i}>
                {m.role === "user" ? (
                  <p className="text-2xl font-semibold text-white/90 leading-snug">{m.content}</p>
                ) : (
                  <div className="flex gap-3 mt-2">
                    <div className="mt-1 shrink-0 w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
                      <ShieldCheck size={13} className="text-indigo-400" />
                    </div>
                    <p className="text-[15px] leading-relaxed text-white/75 whitespace-pre-wrap">{m.content}</p>
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
        /* Hero — shown before first message */
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

      {/* Pinned input bar */}
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
            Powered by DeepSeek via OpenRouter · DS Fusion scoring · 87 suppliers indexed
          </p>
        </div>
      </div>
    </div>
  );
}
