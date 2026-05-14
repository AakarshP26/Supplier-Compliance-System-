"use client";

import { useState, useRef, useEffect } from "react";
import { ShineBorder } from "@/components/ui/shine-border";
import axios from "axios";

export function CopilotSidebar() {
  const [messages, setMessages] = useState<{ role: string; content: string }[]>([
    { role: "assistant", content: "I'm your Supplier Compliance assistant. How can I help you today?" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const res = await axios.post("http://localhost:8000/api/agent/chat", {
        message: userMsg,
        history: messages,
        context: { page: window.location.pathname },
      });
      setMessages((prev) => [...prev, { role: "assistant", content: res.data.reply }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error connecting to backend." }]);
    }
    setLoading(false);
  };

  return (
    <div className="w-[400px] border-l border-white/5 flex flex-col bg-black/40 relative h-full">
      <ShineBorder 
        className="absolute inset-0 pointer-events-none rounded-none border-0" 
        color="#A07CFE"
      />
      
      <div className="p-6 border-b border-white/5 relative z-10 bg-black/60 backdrop-blur-xl">
        <h3 className="font-medium tracking-tight text-white flex items-center gap-3">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
          </span>
          Compliance Copilot
        </h3>
        <p className="text-xs text-white/40 mt-1">Llama-3.1-8B via OpenRouter</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 relative z-10 scroll-smooth" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-5 py-3 shadow-sm ${
              m.role === 'user' 
                ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white shadow-indigo-500/20' 
                : 'bg-white/[0.02] border border-white/5 text-white/80 backdrop-blur-sm'
            }`}>
              <p className="text-[13px] leading-relaxed whitespace-pre-wrap font-light">{m.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white/[0.02] border border-white/5 rounded-2xl px-5 py-4 flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" />
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-.15s]" />
              <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce [animation-delay:-.3s]" />
            </div>
          </div>
        )}
      </div>

      <div className="p-6 relative z-10 bg-black/60 backdrop-blur-xl border-t border-white/5">
        <div className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-xl blur opacity-20 group-hover:opacity-40 transition duration-500"></div>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder="Command the agent..."
            className="relative w-full bg-black border border-white/10 rounded-xl pl-5 pr-12 py-4 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500/50 transition-all text-white placeholder:text-white/30 font-light"
          />
          <button 
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="absolute right-3 top-1/2 -translate-y-1/2 p-2 bg-white/5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-all disabled:opacity-50"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          </button>
        </div>
      </div>
    </div>
  );
}