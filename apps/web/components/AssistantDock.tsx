"use client";

import { useState, useRef, useEffect } from "react";

import { getBrowserApiBaseUrl } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function AssistantDock() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await fetch(`${getBrowserApiBaseUrl()}/api/v1/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q }),
      });
      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer ?? "No response." }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Failed to reach the assistant. Is the API running?" }]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-info shadow-lg transition-transform hover:scale-105"
        aria-label="Open AI assistant"
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex h-[480px] w-[380px] flex-col rounded-lg border border-terminal-border bg-terminal-bg shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-terminal-border px-4 py-2.5">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-white">Research Assistant</span>
        </div>
        <button onClick={() => setOpen(false)} className="text-terminal-muted hover:text-white" aria-label="Close">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-xs text-terminal-muted mt-4 text-center">
            <p>Ask me about any tracked instrument.</p>
            <p className="mt-1 italic">&quot;Which products have the highest score?&quot;</p>
            <p className="italic">&quot;What&apos;s the risk on Prismatic Evolutions ETB?&quot;</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-info/20 text-white"
                  : "bg-terminal-panel text-slate-300"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-lg bg-terminal-panel px-3 py-2 text-sm text-terminal-muted animate-pulse">
              Thinking...
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-terminal-border p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Ask about instruments..."
            className="flex-1 rounded border border-terminal-border bg-terminal-panel px-3 py-2 text-sm text-white placeholder-terminal-muted focus:border-info focus:outline-none"
            disabled={loading}
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="rounded bg-info px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            Send
          </button>
        </div>
        <div className="mt-1.5 text-[10px] text-terminal-muted">
          Powered by Groq (free models). Research only, not investment advice.
        </div>
      </div>
    </div>
  );
}
