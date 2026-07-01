import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
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
};

type ToolSlug = "coding" | "monitoring" | "research";

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

type MonitoringStreamEvent = {
  type?: string;
  content?: string;
  shell?: string;
  cwd?: string;
  returncode?: number;
};

type MonitoringInsight = {
  id: string;
  content: string;
  createdAt: string;
  isStreaming?: boolean;
};

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

const TOOL_CATALOG: Array<{
  id: ToolSlug;
  label: string;
  title: string;
  description: string;
  status: string;
}> = [
  {
    id: "coding",
    label: "Code",
    title: "Coding",
    description:
      "Copilot-style coding assistant with streaming plan, tool calls, and final output.",
    status: "Ready",
  },
  {
    id: "monitoring",
    label: "Watch",
    title: "Monitoring",
    description:
      "Track runtime health, active tasks, logs, and system signals for local tools.",
    status: "Ready",
  },
  {
    id: "research",
    label: "Read",
    title: "Research",
    description:
      "Gather references, compare options, and organize findings for implementation work.",
    status: "Setup",
  },
];

function parseToolFromHash(hash: string): ToolSlug {
  const normalized = hash.replace(/^#\/?/, "").toLowerCase();
  if (normalized === "monitoring") return "monitoring";
  if (normalized === "research") return "research";
  return "coding";
}

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

function shouldRenderMarkdown(event: StreamEvent) {
  const markdownTypes = new Set(["assistant_message", "plan", "final"]);
  return markdownTypes.has(event.type ?? "");
}

export default function App() {
  const [path, setPath] = useState("C:/Users/Krish/project/localcoder");
  const [query, setQuery] = useState("");
  const [model, setModel] = useState("qwen3.6");
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTool, setActiveTool] = useState<ToolSlug>(() =>
    parseToolFromHash(window.location.hash)
  );
  const [monitoringCommand, setMonitoringCommand] = useState(
    "while ($true) { Get-Date; Start-Sleep -Seconds 2 }"
  );
  const [monitoringContext, setMonitoringContext] = useState("");
  const [isMonitoringActive, setIsMonitoringActive] = useState(false);
  const [liveStdout, setLiveStdout] = useState("");
  const [liveStderr, setLiveStderr] = useState("");
  const [streamMeta, setStreamMeta] = useState<{ shell?: string; cwd?: string }>(
    {}
  );
  const [streamReturncode, setStreamReturncode] = useState<number | null>(null);
  const [monitoringInsights, setMonitoringInsights] = useState<MonitoringInsight[]>(
    []
  );
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [monitoringError, setMonitoringError] = useState<string | null>(null);
  const [agentInsightsEnabled, setAgentInsightsEnabled] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const monitoringContainerRef = useRef<HTMLDivElement | null>(null);
  const insightsContainerRef = useRef<HTMLDivElement | null>(null);
  const streamAbortRef = useRef<AbortController | null>(null);
  const analyzeAbortRef = useRef<AbortController | null>(null);
  const analyzeIntervalRef = useRef<number | null>(null);
  const lastAnalyzedLengthRef = useRef(0);
  const logsSnapshotRef = useRef({ stdout: "", stderr: "" });
  const monitoringContextRef = useRef("");
  const agentInsightsEnabledRef = useRef(false);
  const activeCommandRef = useRef("");

  const canSubmit = useMemo(() => {
    return path.trim().length > 0 && query.trim().length > 0 && !isStreaming;
  }, [isStreaming, path, query]);

  const userMessageCount = useMemo(
    () => feed.filter((item) => item.role === "user").length,
    [feed]
  );

  const agentEventCount = useMemo(
    () => feed.filter((item) => item.role === "agent").length,
    [feed]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [feed]);

  useEffect(() => {
    const container = monitoringContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [liveStdout, liveStderr]);

  useEffect(() => {
    const container = insightsContainerRef.current;
    if (!container) return;
    container.scrollTop = container.scrollHeight;
  }, [monitoringInsights]);

  useEffect(() => {
    logsSnapshotRef.current = { stdout: liveStdout, stderr: liveStderr };
  }, [liveStdout, liveStderr]);

  useEffect(() => {
    monitoringContextRef.current = monitoringContext;
  }, [monitoringContext]);

  useEffect(() => {
    agentInsightsEnabledRef.current = agentInsightsEnabled;
  }, [agentInsightsEnabled]);

  useEffect(() => {
    return () => {
      streamAbortRef.current?.abort();
      analyzeAbortRef.current?.abort();
      if (analyzeIntervalRef.current !== null) {
        window.clearInterval(analyzeIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      setActiveTool(parseToolFromHash(window.location.hash));
    };

    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  function navigateToTool(tool: ToolSlug) {
    const nextHash = `#/${tool}`;
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash;
      return;
    }
    setActiveTool(tool);
  }

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

  async function consumeSseStream(
    response: Response,
    onPayload: (payload: Record<string, unknown>) => void
  ) {
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
        onPayload(JSON.parse(dataLines.join("\n")));
      }
    }

    const remaining = buffer.trim();
    if (remaining.startsWith("data: ")) {
      onPayload(JSON.parse(remaining.slice(6)));
    }
  }

  function stopAnalyzeInterval() {
    analyzeAbortRef.current?.abort();
    analyzeAbortRef.current = null;
    setIsAnalyzing(false);

    if (analyzeIntervalRef.current !== null) {
      window.clearInterval(analyzeIntervalRef.current);
      analyzeIntervalRef.current = null;
    }
  }

  function startAnalyzeInterval(command: string) {
    if (!agentInsightsEnabledRef.current) return;

    stopAnalyzeInterval();
    analyzeIntervalRef.current = window.setInterval(() => {
      void requestMonitoringInsight(command);
    }, 12000);
  }

  function stopMonitoringStream(abortAnalyze = false) {
    streamAbortRef.current?.abort();
    streamAbortRef.current = null;

    if (analyzeIntervalRef.current !== null) {
      window.clearInterval(analyzeIntervalRef.current);
      analyzeIntervalRef.current = null;
    }

    if (abortAnalyze) {
      analyzeAbortRef.current?.abort();
      analyzeAbortRef.current = null;
      setIsAnalyzing(false);
    }

    setIsMonitoringActive(false);
    activeCommandRef.current = "";
  }

  function stopMonitoringSession() {
    stopMonitoringStream(true);
  }

  async function requestMonitoringInsight(command: string, force = false) {
    if (!agentInsightsEnabledRef.current) return;

    const { stdout, stderr } = logsSnapshotRef.current;
    const combinedLogs = `${stdout}${stderr}`;
    const nextLength = combinedLogs.length;

    if (!force && nextLength <= lastAnalyzedLengthRef.current) {
      return;
    }

    lastAnalyzedLengthRef.current = nextLength;
    analyzeAbortRef.current?.abort();
    const abortController = new AbortController();
    analyzeAbortRef.current = abortController;

    const insightId = createId();
    setIsAnalyzing(true);
    setMonitoringInsights((current) => [
      ...current,
      {
        id: insightId,
        content: "",
        createdAt: new Date().toISOString(),
        isStreaming: true,
      },
    ]);

    try {
      const response = await fetch(`${API_BASE_URL}/monitoring/analyze/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: abortController.signal,
        body: JSON.stringify({
          command,
          cwd: path.trim() || undefined,
          logs: combinedLogs,
          model,
          context: monitoringContextRef.current.trim() || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error(`Insight request failed with status ${response.status}`);
      }

      await consumeSseStream(response, (payload) => {
        if (payload.type === "insight_delta" && typeof payload.content === "string") {
          setMonitoringInsights((current) =>
            current.map((item) =>
              item.id === insightId
                ? { ...item, content: item.content + payload.content }
                : item
            )
          );
        }

        if (payload.type === "insight_done") {
          setMonitoringInsights((current) =>
            current.map((item) =>
              item.id === insightId ? { ...item, isStreaming: false } : item
            )
          );
        }

        if (payload.type === "insight_error" && typeof payload.message === "string") {
          setMonitoringInsights((current) =>
            current.map((item) =>
              item.id === insightId
                ? {
                    ...item,
                    content: payload.message as string,
                    isStreaming: false,
                  }
                : item
            )
          );
        }
      });
    } catch (insightError) {
      if (
        abortController.signal.aborted ||
        (insightError instanceof DOMException && insightError.name === "AbortError")
      ) {
        setMonitoringInsights((current) =>
          current.filter((item) => item.id !== insightId || item.content.length > 0)
        );
        return;
      }

      const message =
        insightError instanceof Error
          ? insightError.message
          : "Unknown insight error";

      setMonitoringInsights((current) =>
        current.map((item) =>
          item.id === insightId
            ? {
                ...item,
                content: message,
                isStreaming: false,
              }
            : item
        )
      );
    } finally {
      if (analyzeAbortRef.current === abortController) {
        analyzeAbortRef.current = null;
      }
      setIsAnalyzing(false);
    }
  }

  async function startMonitoringSession(command: string) {
    setMonitoringError(null);
    setLiveStdout("");
    setLiveStderr("");
    setStreamMeta({});
    setStreamReturncode(null);
    setMonitoringInsights([]);
    lastAnalyzedLengthRef.current = 0;
    logsSnapshotRef.current = { stdout: "", stderr: "" };

    streamAbortRef.current?.abort();
    const abortController = new AbortController();
    streamAbortRef.current = abortController;

    setIsMonitoringActive(true);
    activeCommandRef.current = command;

    if (agentInsightsEnabledRef.current) {
      startAnalyzeInterval(command);
    }

    let sessionStdout = "";
    let sessionStderr = "";

    try {
      const response = await fetch(`${API_BASE_URL}/monitoring/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: abortController.signal,
        body: JSON.stringify({
          command,
          cwd: path.trim() || undefined,
        }),
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(
            "Monitoring stream endpoint not found. Restart backend with: uvicorn api:app --reload"
          );
        }
        throw new Error(`Monitoring stream failed with status ${response.status}`);
      }

      await consumeSseStream(response, (payload) => {
        const event = payload as MonitoringStreamEvent;

        if (event.type === "start") {
          setStreamMeta({ shell: event.shell, cwd: event.cwd });
          return;
        }

        if (event.type === "cwd" && event.cwd) {
          setPath(event.cwd);
          setStreamMeta((current) => ({ ...current, cwd: event.cwd }));
          setMonitoringCommand("");
          return;
        }

        if (event.type === "stdout" && event.content) {
          sessionStdout += event.content;
          logsSnapshotRef.current = {
            stdout: sessionStdout,
            stderr: sessionStderr,
          };
          setLiveStdout(sessionStdout);
          return;
        }

        if (event.type === "stderr" && event.content) {
          sessionStderr += event.content;
          logsSnapshotRef.current = {
            stdout: sessionStdout,
            stderr: sessionStderr,
          };
          setLiveStderr(sessionStderr);
          return;
        }

        if (event.type === "end" && typeof event.returncode === "number") {
          setStreamReturncode(event.returncode);
          stopMonitoringStream(false);
          if (agentInsightsEnabledRef.current) {
            void requestMonitoringInsight(command, true);
          }
        }
      });
    } catch (streamError) {
      if (streamError instanceof DOMException && streamError.name === "AbortError") {
        return;
      }

      const message =
        streamError instanceof Error
          ? streamError.message
          : "Unknown monitoring stream error";

      setMonitoringError(message);
      stopMonitoringStream(true);
    } finally {
      if (streamAbortRef.current === abortController) {
        streamAbortRef.current = null;
      }
      setIsMonitoringActive(false);
    }
  }

  function handleAgentInsightsModeChange(enabled: boolean) {
    agentInsightsEnabledRef.current = enabled;
    setAgentInsightsEnabled(enabled);

    if (!enabled) {
      stopAnalyzeInterval();
      return;
    }

    if (isMonitoringActive && activeCommandRef.current) {
      startAnalyzeInterval(activeCommandRef.current);
    }
  }

  function handleCommandRun() {
    if (isMonitoringActive) {
      stopMonitoringSession();
      return;
    }

    const command = monitoringCommand.trim();
    if (!command) {
      setMonitoringError("Enter a command before running.");
      return;
    }

    void startMonitoringSession(command);
  }

  return (
    <div className="app-shell">
      <div className="app-layout">
        <aside className="tool-sidebar" aria-label="Tools">
          <div className="tool-sidebar-brand" title="Coolbot">
            <span className="tool-sidebar-logo">CB</span>
          </div>
          <nav className="tool-nav">
            {TOOL_CATALOG.map((tool) => {
              const isActive = activeTool === tool.id;
              return (
                <button
                  key={tool.id}
                  type="button"
                  className={`tool-nav-item ${isActive ? "tool-nav-item-active" : ""}`}
                  onClick={() => navigateToTool(tool.id)}
                  title={`${tool.title} — ${tool.description}`}
                  aria-current={isActive ? "page" : undefined}
                >
                  <span className="tool-nav-label">{tool.label}</span>
                  <span
                    className={`tool-nav-status ${
                      tool.status === "Ready"
                        ? "tool-nav-status-ready"
                        : "tool-nav-status-setup"
                    }`}
                    aria-hidden="true"
                  />
                </button>
              );
            })}
          </nav>
        </aside>

        <main
          className={`app-main ${
            activeTool === "coding" ? "app-main-coding" : "app-main-tool"
          }`}
        >
          <header className="app-header">
            <div className="app-header-title">
              <h1 className="app-title">Coolbot</h1>
              <span className="app-subtitle">Your local copilot</span>
            </div>
            <div className="header-chips" aria-label="Session overview">
              <span className="chip">Model: {model}</span>
              <span className="chip">Prompts: {userMessageCount}</span>
              <span className="chip">Events: {agentEventCount}</span>
              <span className={`chip ${isStreaming ? "chip-live" : "chip-idle"}`}>
                {isStreaming ? "Live" : "Idle"}
              </span>
            </div>
          </header>

        {activeTool !== "coding" ? (
          <section
            className={`tool-landing ${
              activeTool === "monitoring" ? "tool-landing-monitoring" : ""
            }`}
            aria-label={`${activeTool} tool`}
          >
            <h2 className="tool-landing-title">
              {activeTool === "monitoring" ? "Monitoring" : "Research"}
            </h2>
            {activeTool === "monitoring" ? (
              <div className="monitoring-layout">
                <div className="monitoring-main">
                  <p className="tool-landing-text">
                    Run a shell command and stream output in real time. Enable agent
                    insights when you want the model to analyze logs.
                  </p>

                  {agentInsightsEnabled ? (
                    <label className="field monitoring-context-field">
                      <span className="field-label">What are we debugging today?</span>
                      <textarea
                        value={monitoringContext}
                        onChange={(event) => setMonitoringContext(event.target.value)}
                        placeholder="Describe the issue, expected behavior, and what you have tried so far"
                        rows={3}
                        className="field-control field-textarea monitoring-context-control"
                        disabled={isMonitoringActive}
                      />
                    </label>
                  ) : null}

                  <label className="field monitoring-path-field">
                    <span className="field-label">Working directory</span>
                    <input
                      value={path}
                      onChange={(event) => setPath(event.target.value)}
                      placeholder="Project path"
                      className="field-control"
                      disabled={isMonitoringActive}
                    />
                  </label>

                  <label className="field monitoring-command-field">
                    <span className="field-label">Command</span>
                    <input
                      value={monitoringCommand}
                      onChange={(event) => setMonitoringCommand(event.target.value)}
                      placeholder="e.g. ls, Get-ChildItem, or a watch loop"
                      className="field-control monitoring-command-control"
                      disabled={isMonitoringActive}
                    />
                  </label>

                  <div className="monitoring-run-row">
                    <button
                      type="button"
                      className={`send-button monitoring-run-button ${
                        isMonitoringActive ? "monitoring-toggle-stop" : ""
                      }`}
                      onClick={handleCommandRun}
                      disabled={!isMonitoringActive && !monitoringCommand.trim()}
                    >
                      {isMonitoringActive ? "Stop" : "Run command"}
                    </button>
                  </div>

                  <div className="monitoring-status-row">
                    <span
                      className={`chip ${isMonitoringActive ? "chip-live" : "chip-idle"}`}
                    >
                      {isMonitoringActive ? "Running" : "Idle"}
                    </span>
                    {streamMeta.shell || streamMeta.cwd ? (
                      <span className="monitoring-meta">
                        {streamMeta.shell ? `shell: ${streamMeta.shell}` : ""}
                        {streamMeta.shell && streamMeta.cwd ? " · " : ""}
                        {streamMeta.cwd ? `cwd: ${streamMeta.cwd}` : ""}
                      </span>
                    ) : null}
                    {streamReturncode !== null ? (
                      <span className="monitoring-exit">
                        exit code: {streamReturncode}
                      </span>
                    ) : null}
                  </div>

                  <div ref={monitoringContainerRef} className="monitoring-output">
                    {!liveStdout && !liveStderr ? (
                      <div className="monitoring-placeholder">
                        Output will appear here after you run a command.
                      </div>
                    ) : null}
                    {liveStdout ? (
                      <pre className="monitoring-stdout">{liveStdout}</pre>
                    ) : null}
                    {liveStderr ? (
                      <pre className="monitoring-stderr">{liveStderr}</pre>
                    ) : null}
                  </div>

                  {monitoringError ? (
                    <span className="error-text">{monitoringError}</span>
                  ) : null}
                </div>

                <aside className="monitoring-sidebar" aria-label="Monitoring agent">
                  <div className="monitoring-sidebar-header">
                    <h3 className="monitoring-sidebar-title">Agent insights</h3>
                    <p className="monitoring-sidebar-subtitle">
                      Optional AI analysis of command output while it runs.
                    </p>
                  </div>

                  <fieldset
                    className="monitoring-mode-fieldset"
                    disabled={isMonitoringActive}
                  >
                    <legend className="monitoring-mode-legend">Mode</legend>
                    <div className="monitoring-mode-options">
                      <label className="monitoring-mode-option">
                        <input
                          type="radio"
                          name="monitoring-mode"
                          checked={!agentInsightsEnabled}
                          onChange={() => handleAgentInsightsModeChange(false)}
                        />
                        <span>Output only</span>
                      </label>
                      <label className="monitoring-mode-option">
                        <input
                          type="radio"
                          name="monitoring-mode"
                          checked={agentInsightsEnabled}
                          onChange={() => handleAgentInsightsModeChange(true)}
                        />
                        <span>With agent</span>
                      </label>
                    </div>
                  </fieldset>

                  {agentInsightsEnabled ? (
                    <label className="field monitoring-model-field">
                      <span className="field-label">Model</span>
                      <select
                        value={model}
                        onChange={(event) => setModel(event.target.value)}
                        disabled={isMonitoringActive || isAnalyzing}
                        className="field-control"
                      >
                        {AVAILABLE_MODELS.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}

                  <div ref={insightsContainerRef} className="monitoring-insights">
                    {!agentInsightsEnabled ? (
                      <div className="monitoring-insight-placeholder">
                        Output only mode — run commands like <code>ls</code> without
                        calling the model. Switch to &ldquo;With agent&rdquo; for live
                        analysis.
                      </div>
                    ) : monitoringInsights.length === 0 ? (
                      <div className="monitoring-insight-placeholder">
                        Run a command to get guidance on what to watch for in the
                        output.
                      </div>
                    ) : null}

                    {agentInsightsEnabled
                      ? monitoringInsights.map((insight) => (
                      <article key={insight.id} className="monitoring-insight-card">
                        <div className="monitoring-insight-meta">
                          <span>Agent insight</span>
                          <span>
                            {new Date(insight.createdAt).toLocaleTimeString()}
                            {insight.isStreaming ? " · live" : ""}
                          </span>
                        </div>
                        <MarkdownViewer
                          content={
                            insight.content ||
                            (insight.isStreaming ? "Analyzing output..." : "")
                          }
                          className="monitoring-insight-body markdown-body"
                        />
                      </article>
                    ))
                      : null}
                  </div>
                </aside>
              </div>
            ) : (
              <p className="tool-landing-text">
                Research tool page is active. Next step can be adding source
                discovery, notes, and citation workflows.
              </p>
            )}
          </section>
        ) : null}

        {activeTool === "coding" ? (
          <form onSubmit={handleSubmit} className="chat-form">
          <label className="field">
            <span className="field-label">Path</span>
            <input
              value={path}
              onChange={(event) => setPath(event.target.value)}
              placeholder="Project path"
              className="field-control"
            />
          </label>

          <label className="field">
            <span className="field-label">Model</span>
            <select
              value={model}
              onChange={(event) => setModel(event.target.value)}
              disabled={isStreaming}
              className="field-control"
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span className="field-label">Query</span>
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tell the agent what to do"
              rows={4}
              className="field-control field-textarea"
            />
          </label>

          <div className="form-actions">
            <button
              type="submit"
              disabled={!canSubmit}
              className="send-button"
            >
              {isStreaming ? "Working..." : "Send"}
            </button>
            <span className="api-hint">
              API: {API_BASE_URL}
            </span>
          </div>
          {error ? <span className="error-text">{error}</span> : null}
          </form>
        ) : null}

        {activeTool === "coding" ? (
          <section ref={containerRef} className="feed-panel">
          {feed.length === 0 ? (
            <div className="empty-feed">
              <h2 className="empty-title">No events yet</h2>
              <p className="empty-text">
                Enter a path and prompt, then click Send to watch the agent stream
                planning, tool calls, and final results in real time.
              </p>
            </div>
          ) : null}

          {feed.map((item) => {
            if (item.role === "user") {
              return (
                <article key={item.id} className="feed-item feed-item-user">
                  <div className="feed-item-meta feed-item-meta-user">
                    You - {new Date(item.createdAt).toLocaleTimeString()}
                    {" - "}Model: {item.model}
                  </div>
                  <div className="feed-item-user-query">{item.query}</div>
                  <div className="feed-item-user-path">{item.path}</div>
                </article>
              );
            }

            const label = formatEventLabel(item.event);
            const body = formatEventBody(item.event);
            const isError = item.event.type === "error";
            const useMarkdown = shouldRenderMarkdown(item.event);

            return (
              <article
                key={item.id}
                className={`feed-item feed-item-agent ${
                  isError ? "feed-item-agent-error" : ""
                }`}
              >
                <div className="feed-item-meta">
                  <span>{label}</span>
                  <span>{new Date(item.createdAt).toLocaleTimeString()}</span>
                </div>
                {useMarkdown ? (
                  <MarkdownViewer
                    content={body}
                    className={`feed-body markdown-body ${
                      isError ? "feed-body-error" : ""
                    }`}
                  />
                ) : (
                  <pre
                    className={`feed-body ${isError ? "feed-body-error" : ""}`}
                  >
                    {body}
                  </pre>
                )}
              </article>
            );
          })}
          </section>
        ) : null}
        </main>
      </div>
    </div>
  );
}
