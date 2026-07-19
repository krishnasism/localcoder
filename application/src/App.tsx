import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";
import { MarkdownViewer } from "./MarkdownViewer";
import "./App.css";

type StreamEvent = {
  type?: string;
  step?: string;
  message?: string;
  content?: string;
  tool?: string;
  result?: string;
  summary?: string;
  args?: Record<string, unknown>;
  blocked?: boolean;
  iteration?: number;
  max_iterations?: number;
};

type UserMessage = {
  id: string;
  role: "user";
  query: string;
  path: string;
  model: string;
  createdAt: string;
};

type AgentActivity = {
  id: string;
  role: "agent";
  kind: "status" | "message" | "plan" | "tool" | "final" | "error";
  title: string;
  step?: string;
  body?: string;
  tool?: string;
  result?: string;
  blocked?: boolean;
  collapsed?: boolean;
  createdAt: string;
};

type FeedItem = UserMessage | AgentActivity;

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  "http://127.0.0.1:8000";

const AVAILABLE_MODELS = [
  "qwen3.6",
  "qwen2.5:7b",
  "llama-3.2",
  "llama2-uncensored:7b",
  "dolphin3:8b",
];

const DEFAULT_PATH =
  typeof window !== "undefined"
    ? window.localStorage.getItem("localcoder.path") ??
      "C:/Users/Krish/project/localcoder"
    : "C:/Users/Krish/project/localcoder";

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function phaseLabel(step?: string) {
  if (!step) return "Idle";
  if (step === "planning" || step === "initializing") return "Planning";
  if (step === "editing") return "Editing";
  if (step === "completed") return "Done";
  if (step === "cancelled") return "Cancelled";
  return step;
}

function shortenPath(path: string) {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  if (parts.length <= 3) return path;
  return `…/${parts.slice(-3).join("/")}`;
}

function formatToolArgs(args?: Record<string, unknown>) {
  if (!args || Object.keys(args).length === 0) return "";
  return Object.entries(args)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join(" · ");
}

function describeLiveStatus(event: StreamEvent): string | null {
  if (event.type === "tool_start" && event.tool) {
    const filename = String(
      event.args?.filename ?? event.args?.path ?? event.args?.src ?? ""
    );
    const short = filename ? filename.replace(/^.*[/\\]/, "") : "";
    switch (event.tool) {
      case "read_file":
        return short ? `Reading ${short}…` : "Reading file…";
      case "sed":
        return short ? `Editing ${short}…` : "Editing file…";
      case "insert_after":
        return short ? `Inserting into ${short}…` : "Inserting lines…";
      case "write_file":
        return short ? `Writing ${short}…` : "Writing file…";
      case "pytest":
      case "pytest_with_coverage":
        return "Running tests…";
      case "search_text_in_files":
        return "Searching codebase…";
      case "find_files":
        return "Finding files…";
      case "plan_finish":
        return "Finalizing plan…";
      case "finish":
        return "Wrapping up…";
      default:
        return short ? `${event.tool} · ${short}…` : `Running ${event.tool}…`;
    }
  }

  if (event.type === "tool_result" && event.tool) {
    if (event.blocked) return `${event.tool} blocked — trying another approach…`;
    return `Finished ${event.tool}`;
  }

  if (event.type === "status" && event.message) {
    return event.message;
  }

  if (event.type === "assistant_message") {
    return "Thinking…";
  }

  if (event.type === "plan") {
    return "Plan ready — starting edits…";
  }

  if (event.type === "final") {
    return "Done";
  }

  if (event.type === "error") {
    return event.message ?? "Error";
  }

  return null;
}

function eventToActivity(event: StreamEvent): AgentActivity | null {
  const createdAt = new Date().toISOString();
  const id = createId();

  if (event.type === "assistant_message" && event.content) {
    return {
      id,
      role: "agent",
      kind: "message",
      title: "Assistant",
      step: event.step,
      body: event.content,
      createdAt,
    };
  }

  if (event.type === "plan" && event.content) {
    return {
      id,
      role: "agent",
      kind: "plan",
      title: "Plan",
      step: event.step,
      body: event.content,
      createdAt,
    };
  }

  if (event.type === "tool_start" && event.tool) {
    return {
      id,
      role: "agent",
      kind: "tool",
      title: event.tool,
      step: event.step,
      tool: event.tool,
      body: formatToolArgs(event.args),
      collapsed: true,
      createdAt,
    };
  }

  if (event.type === "tool_result" && event.tool) {
    return {
      id,
      role: "agent",
      kind: "tool",
      title: event.tool,
      step: event.step,
      tool: event.tool,
      result: event.result,
      blocked: event.blocked,
      collapsed: true,
      createdAt,
    };
  }

  if (event.type === "final") {
    return {
      id,
      role: "agent",
      kind: "final",
      title: "Completed",
      step: event.step,
      body: event.summary ?? event.message ?? "Done.",
      createdAt,
    };
  }

  if (event.type === "error") {
    return {
      id,
      role: "agent",
      kind: "error",
      title: "Error",
      step: event.step,
      body: event.message ?? "Unknown error",
      createdAt,
    };
  }

  if (event.type === "status") {
    // Skip noisy per-iteration status lines; keep phase transitions and special notes.
    const message = event.message ?? "";
    if (/iteration|step \d+/i.test(message) && !/completed|fallback|wrapping|cancelled/i.test(message)) {
      return null;
    }
    return {
      id,
      role: "agent",
      kind: "status",
      title: phaseLabel(event.step),
      step: event.step,
      body: message,
      createdAt,
    };
  }

  return {
    id,
    role: "agent",
    kind: "status",
    title: event.type ?? "Event",
    step: event.step,
    body: event.message ?? event.content ?? JSON.stringify(event),
    createdAt,
  };
}

export default function App() {
  const [path, setPath] = useState(DEFAULT_PATH);
  const [query, setQuery] = useState("");
  const [model, setModel] = useState(
    () => window.localStorage.getItem("localcoder.model") ?? "qwen3.6"
  );
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [phase, setPhase] = useState("Idle");
  const [liveStatus, setLiveStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("dark");
  const toggleTheme = () =>
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  const feedRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const canSubmit = useMemo(() => {
    return path.trim().length > 0 && query.trim().length > 0 && !isStreaming;
  }, [isStreaming, path, query]);

  useEffect(() => {
    window.localStorage.setItem("localcoder.path", path);
  }, [path]);

  useEffect(() => {
    window.localStorage.setItem("localcoder.model", model);
  }, [model]);

  useEffect(() => {
    const container = feedRef.current;
    if (!container) return;
    // Keep the latest message in view without fighting manual scroll-up.
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    if (distanceFromBottom < 160 || isStreaming) {
      container.scrollTop = container.scrollHeight;
    }
  }, [feed, isStreaming]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  function appendActivity(event: StreamEvent) {
    if (event.step) {
      setPhase(phaseLabel(event.step));
    }

    const status = describeLiveStatus(event);
    if (status) {
      setLiveStatus(status);
    }

    const activity = eventToActivity(event);
    if (!activity) return;

    setFeed((current) => {
      if (activity.kind === "tool" && event.type === "tool_result") {
        const next = [...current];
        for (let index = next.length - 1; index >= 0; index -= 1) {
          const item = next[index];
          if (
            item.role === "agent" &&
            item.kind === "tool" &&
            item.tool === activity.tool &&
            !item.result
          ) {
            next[index] = {
              ...item,
              result: activity.result,
              blocked: activity.blocked,
              title: activity.blocked ? `${activity.tool} (blocked)` : activity.tool ?? item.title,
            };
            return next;
          }
        }
      }
      return [...current, activity];
    });
  }

  function handleStop() {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
    setPhase("Cancelled");
    setLiveStatus("");
    setFeed((current) => [
      ...current,
      {
        id: createId(),
        role: "agent",
        kind: "status",
        title: "Cancelled",
        step: "cancelled",
        body: "Run stopped by user.",
        createdAt: new Date().toISOString(),
      },
    ]);
  }

  function handleClear() {
    if (isStreaming) return;
    setFeed([]);
    setError(null);
    setPhase("Idle");
    setLiveStatus("");
  }

  async function handleSubmit(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!canSubmit) return;

    const trimmedPath = path.trim();
    const trimmedQuery = query.trim();

    setError(null);
    setIsStreaming(true);
    setPhase("Planning");
    setLiveStatus("Starting…");
    setQuery("");
    setFeed((current) => [
      ...current,
      {
        id: createId(),
        role: "user",
        path: trimmedPath,
        query: trimmedQuery,
        model,
        createdAt: new Date().toISOString(),
      },
    ]);

    const abortController = new AbortController();
    abortRef.current = abortController;

    try {
      const response = await fetch(`${API_BASE_URL}/generate_code/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: abortController.signal,
        body: JSON.stringify({
          path: trimmedPath,
          query: trimmedQuery,
          model,
        }),
      });

      if (!response.ok) {
        let detail = `Request failed with status ${response.status}`;
        try {
          const payload = await response.json();
          if (typeof payload.detail === "string") detail = payload.detail;
        } catch {
          // ignore
        }
        throw new Error(detail);
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
          appendActivity(payload);
        }
      }

      const remaining = buffer.trim();
      if (remaining.startsWith("data: ")) {
        appendActivity(JSON.parse(remaining.slice(6)) as StreamEvent);
      }

      setPhase((current) => (current === "Cancelled" ? current : "Done"));
    } catch (streamError) {
      if (
        abortController.signal.aborted ||
        (streamError instanceof DOMException && streamError.name === "AbortError")
      ) {
        return;
      }

      const message =
        streamError instanceof Error
          ? streamError.message
          : "Unknown streaming error";

      setError(message);
      setPhase("Error");
      setFeed((current) => [
        ...current,
        {
          id: createId(),
          role: "agent",
          kind: "error",
          title: "Error",
          step: "frontend",
          body: message,
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      if (abortRef.current === abortController) {
        abortRef.current = null;
      }
      setIsStreaming(false);
      setLiveStatus("");
      textareaRef.current?.focus();
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  function toggleTool(id: string) {
    setFeed((current) =>
      current.map((item) =>
        item.role === "agent" && item.id === id
          ? { ...item, collapsed: !item.collapsed }
          : item
      )
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Workspace">
        <div className="sidebar-brand">
          <span className="brand-mark">LC</span>
          <div className="brand-copy">
            <strong>Localcoder</strong>
            <span>Local agent</span>
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Workspace</div>
          <div className="sidebar-path" title={path}>
            {shortenPath(path)}
          </div>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-label">Model</div>
          <div className="sidebar-value">{model}</div>
        </div>

        <div className="sidebar-actions">
          <button
            type="button"
            className="ghost-button"
            onClick={() => setSettingsOpen((open) => !open)}
          >
            {settingsOpen ? "Hide settings" : "Settings"}
          </button>
          <button
            type="button"
            className="ghost-button"
            onClick={handleClear}
            disabled={isStreaming || feed.length === 0}
          >
            Clear chat
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="topbar-left">
            <h1>Agent</h1>
            <span className={`phase-pill phase-${phase.toLowerCase()}`}>
              {isStreaming ? (
                <>
                  <span className="pulse" aria-hidden="true" />
                  {phase}
                </>
              ) : (
                phase
              )}
            </span>
            {isStreaming && liveStatus ? (
              <span className="live-status" title={liveStatus}>
                {liveStatus}
              </span>
            ) : null}
          </div>
          <div className="topbar-right">
            <span className="meta-chip">{feed.filter((i) => i.role === "user").length} prompts</span>
            {isStreaming ? (
              <button type="button" className="stop-button" onClick={handleStop}>
                Stop
              </button>
            ) : null}
          </div>
        </header>

        {settingsOpen ? (
          <section className="settings-bar" aria-label="Settings">
            <label className="setting-field">
              <span>Project path</span>
              <input
                value={path}
                onChange={(event) => setPath(event.target.value)}
                placeholder="Absolute path to your project"
                disabled={isStreaming}
              />
            </label>
            <label className="setting-field setting-field-model">
              <span>Model</span>
              <select
                value={model}
                onChange={(event) => setModel(event.target.value)}
                disabled={isStreaming}
              >
                {AVAILABLE_MODELS.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
          </section>
        ) : null}

        <section ref={feedRef} className="transcript" aria-live="polite">
          {feed.length === 0 ? (
            <div className="empty-state">
              <h2>What should we build?</h2>
              <p>
                Describe a change in the composer below. Localcoder plans, edits
                files in your workspace, and streams progress as it works.
              </p>
              <div className="suggestion-row">
                {[
                  "Add input validation to the generate_code API",
                  "Refactor the agent loop to fail faster on repeated tools",
                  "Improve empty-state copy in the coding UI",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="suggestion-chip"
                    onClick={() => {
                      setQuery(suggestion);
                      textareaRef.current?.focus();
                    }}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {feed.map((item) => {
            if (item.role === "user") {
              return (
                <article key={item.id} className="bubble bubble-user">
                  <div className="bubble-meta">
                    <span>You</span>
                    <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                  </div>
                  <div className="bubble-body">{item.query}</div>
                  <div className="bubble-foot">
                    {shortenPath(item.path)} · {item.model}
                  </div>
                </article>
              );
            }

            if (item.kind === "tool") {
              return (
                <article
                  key={item.id}
                  className={`activity activity-tool ${item.blocked ? "activity-blocked" : ""}`}
                >
                  <button
                    type="button"
                    className="activity-toggle"
                    onClick={() => toggleTool(item.id)}
                  >
                    <span className="activity-icon">›</span>
                    <span className="activity-title">{item.title}</span>
                    {item.body ? <span className="activity-hint">{item.body}</span> : null}
                    <span className="activity-caret">{item.collapsed ? "▸" : "▾"}</span>
                  </button>
                  {!item.collapsed && item.result ? (
                    <pre className="activity-result">{item.result}</pre>
                  ) : null}
                </article>
              );
            }

            const className = [
              "bubble",
              "bubble-agent",
              item.kind === "plan" ? "bubble-plan" : "",
              item.kind === "final" ? "bubble-final" : "",
              item.kind === "error" ? "bubble-error" : "",
              item.kind === "status" ? "bubble-status" : "",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <article key={item.id} className={className}>
                <div className="bubble-meta">
                  <span>{item.title}</span>
                  <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                </div>
                {item.kind === "message" || item.kind === "plan" || item.kind === "final" ? (
                  <MarkdownViewer
                    content={item.body ?? ""}
                    className="bubble-body markdown-body"
                  />
                ) : (
                  <div className="bubble-body">{item.body}</div>
                )}
              </article>
            );
          })}

          {isStreaming ? (
            <div className="thinking-row" aria-live="polite">
              <span className="thinking-dot" />
              <span className="thinking-dot" />
              <span className="thinking-dot" />
              <span>{liveStatus || "Working…"}</span>
            </div>
          ) : null}
        </section>

        <form className="composer" onSubmit={handleSubmit}>
          {!settingsOpen ? (
            <div className="composer-context">
              <button
                type="button"
                className="context-pill"
                onClick={() => setSettingsOpen(true)}
                title={path}
              >
                {shortenPath(path)}
              </button>
              <button
                type="button"
                className="context-pill"
                onClick={() => setSettingsOpen(true)}
              >
                {model}
              </button>
            </div>
          ) : null}

          <div className="composer-box">
            <textarea
              ref={textareaRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Ask Localcoder to plan and edit code…"
              rows={3}
              disabled={isStreaming}
            />
            <div className="composer-actions">
              <span className="composer-hint">Enter to send · Shift+Enter for newline</span>
              {isStreaming ? (
                <button type="button" className="stop-button" onClick={handleStop}>
                  Stop
                </button>
              ) : (
                <button type="submit" className="send-button" disabled={!canSubmit}>
                  Send
                </button>
              )}
            </div>
          </div>
          {error ? <p className="error-banner">{error}</p> : null}
        </form>
      </main>
    </div>
  );
}
