import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type StreamEvent = {
  type?: string;
  step?: string;
  message?: string;
  content?: string;
  tool?: string;
  result?: string;
  summary?: string;
};

type FeedItem =
  | {
      id: string;
      role: "user";
      query: string;
      path: string;
      model: string;
      createdAt: string;
    }
  | {
      id: string;
      role: "agent";
      event: StreamEvent;
      createdAt: string;
    };

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const AVAILABLE_MODELS = [
  "qwen3.6",
  "qwen2.5",
  "gpt-4o",
  "gpt-4o-mini",
  "claude-3.5-sonnet",
  "llama-3.1",
];

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function formatEventLabel(event: StreamEvent) {
  if (event.type === "assistant_message") return "Assistant";
  if (event.type === "tool_start" && event.tool) return `Tool started: ${event.tool}`;
  if (event.type === "tool_result" && event.tool) return `Tool result: ${event.tool}`;
  if (event.type === "plan") return "Plan";
  if (event.type === "error") return "Error";
  if (event.type === "final") return "Done";
  if (event.step && event.message) return `${event.step}`;
  return event.type ?? "Event";
}

function formatEventBody(event: StreamEvent) {
  return (
    event.content ??
    event.message ??
    event.summary ??
    event.result ??
    JSON.stringify(event, null, 2)
  );
}

export default function App() {
  const [path, setPath] = useState("C:/Users/Krish/project/localcoder");
  const [query, setQuery] = useState("");
  const [model, setModel] = useState("qwen3.6");
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const canSubmit = useMemo(() => {
    return path.trim().length > 0 && query.trim().length > 0 && !isStreaming;
  }, [isStreaming, path, query]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [feed]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    const trimmedPath = path.trim();
    const trimmedQuery = query.trim();

    setError(null);
    setIsStreaming(true);
    setFeed((current) => [
      ...current,
      {
        id: createId(),
        role: "user",
        path: trimmedPath,
        query: trimmedQuery,
        model: model,
        createdAt: new Date().toISOString(),
      },
    ]);

    try {
      const response = await fetch(`${API_BASE_URL}/generate_code/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          path: trimmedPath,
          query: trimmedQuery,
          model: model,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      if (!response.body) {
        throw new Error("Streaming response body is not available.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const dataLines = frame
            .split("\n")
            .filter((line) => line.startsWith("data: "))
            .map((line) => line.slice(6));

          if (dataLines.length === 0) continue;

          const payload = JSON.parse(dataLines.join("\n")) as StreamEvent;
          setFeed((current) => [
            ...current,
            {
              id: createId(),
              role: "agent",
              event: payload,
              createdAt: new Date().toISOString(),
            },
          ]);
        }
      }

      const remaining = buffer.trim();
      if (remaining.startsWith("data: ")) {
        const payload = JSON.parse(remaining.slice(6)) as StreamEvent;
        setFeed((current) => [
          ...current,
          {
            id: createId(),
            role: "agent",
            event: payload,
            createdAt: new Date().toISOString(),
          },
        ]);
      }
    } catch (streamError) {
      const message =
        streamError instanceof Error
          ? streamError.message
          : "Unknown streaming error";

      setError(message);
      setFeed((current) => [
        ...current,
        {
          id: createId(),
          role: "agent",
          event: {
            type: "error",
            step: "frontend",
            message,
          },
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsStreaming(false);
      setQuery("");
    }
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0b1020",
        color: "#e5e7eb",
        padding: 24,
        fontFamily:
          'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          display: "grid",
          gap: 16,
        }}
      >
        <header>
          <h1 style={{ margin: 0, fontSize: 28 }}>LocalCoder Chat</h1>
          <p style={{ margin: "8px 0 0", color: "#94a3b8" }}>
            Your friendly and cheap AI Assistant.
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          style={{
            display: "grid",
            gap: 12,
            padding: 16,
            background: "#111827",
            border: "1px solid #1f2937",
            borderRadius: 14,
          }}
        >
          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14, color: "#cbd5e1" }}>Path</span>
            <input
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="Project path"
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                border: "1px solid #334155",
                background: "#020617",
                color: "#f8fafc",
              }}
            />
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14, color: "#cbd5e1" }}>Model</span>
            <select
              value={model}
              onChange={(event) => setModel(event.target.value)}
              disabled={isStreaming}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                border: "1px solid #334155",
                background: "#020617",
                color: "#f8fafc",
              }}
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>

          <label style={{ display: "grid", gap: 6 }}>
            <span style={{ fontSize: 14, color: "#cbd5e1" }}>Query</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tell the agent what to do"
              rows={4}
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                border: "1px solid #334155",
                background: "#020617",
                color: "#f8fafc",
                resize: "vertical",
              }}
            />
          </label>

          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              type="submit"
              disabled={!canSubmit}
              style={{
                padding: "10px 16px",
                borderRadius: 10,
                border: "none",
                background: canSubmit ? "#2563eb" : "#334155",
                color: "white",
                cursor: canSubmit ? "pointer" : "not-allowed",
                fontWeight: 600,
              }}
            >
              {isStreaming ? "Working..." : "Send"}
            </button>
            <span style={{ color: "#94a3b8", fontSize: 14 }}>
              API: {API_BASE_URL}
            </span>
          </div>
          {error ? <span style={{ color: "#fca5a5" }}>{error}</span> : null}
        </form>

        <section
          ref={containerRef}
          style={{
            minHeight: 480,
            maxHeight: "calc(100vh - 280px)",
            overflowY: "auto",
            padding: 16,
            background: "#111827",
            border: "1px solid #1f2937",
            borderRadius: 14,
            display: "grid",
            gap: 12,
          }}
        >
          {feed.length === 0 ? (
            <div style={{ color: "#94a3b8" }}>
              No events yet. Send a request to start streaming.
            </div>
          ) : null}

          {feed.map((item) => {
            if (item.role === "user") {
              return (
                <article
                  key={item.id}
                  style={{
                    justifySelf: "end",
                    maxWidth: "75%",
                    padding: 14,
                    borderRadius: 14,
                    background: "#1d4ed8",
                    color: "#eff6ff",
                  }}
                >
                  <div style={{ fontSize: 12, opacity: 0.8, marginBottom: 6 }}>
                    You • {new Date(item.createdAt).toLocaleTimeString()}
                    {" • "}Model: {item.model}
                  </div>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>{item.query}</div>
                  <div style={{ fontSize: 12, opacity: 0.9 }}>{item.path}</div>
                </article>
              );
            }

            const label = formatEventLabel(item.event);
            const body = formatEventBody(item.event);
            const isError = item.event.type === "error";

            return (
              <article
                key={item.id}
                style={{
                  justifySelf: "start",
                  maxWidth: "85%",
                  padding: 14,
                  borderRadius: 14,
                  background: isError ? "#450a0a" : "#0f172a",
                  border: `1px solid ${isError ? "#7f1d1d" : "#1e293b"}`,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 8,
                    fontSize: 12,
                    color: "#94a3b8",
                  }}
                >
                  <span>{label}</span>
                  <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                </div>
                <pre
                  style={{
                    margin: 0,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    fontFamily:
                      'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace',
                    fontSize: 13,
                    lineHeight: 1.5,
                    color: isError ? "#fecaca" : "#e2e8f0",
                  }}
                >
                  {body}
                </pre>
              </article>
            );
          })}
        </section>
      </div>
    </div>
  );
}
