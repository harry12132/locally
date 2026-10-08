"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  Check,
  CheckCircle2,
  Circle,
  Command,
  FileText,
  Landmark,
  LoaderCircle,
  LockKeyhole,
  Mail,
  MessageSquareText,
  Plus,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_AGENT_API_URL ?? "http://127.0.0.1:8000";

type StreamEvent = {
  agent: string;
  content: string | Record<string, string>;
  type: string;
  thread_id: string;
};

type ChatEntry = {
  id: number;
  role: "user" | "agent" | "activity";
  agent?: string;
  text: string;
};

type EmailDraft = { to: string; subject: string; body: string };

const suggestions = [
  { icon: FileText, text: "Find the late payment clause in our contracts" },
  { icon: Landmark, text: "Check Smith & Co's invoice status" },
  { icon: Mail, text: "Draft an email to Smith & Co about their overdue invoice" },
];

const specialists = [
  { name: "Accounting", detail: "Invoices and balances", icon: Landmark },
  { name: "Legal", detail: "Contract search", icon: FileText },
  { name: "Email drafting", detail: "Approval required", icon: Mail },
];

export default function Home() {
  const [threadId, setThreadId] = useState("");
  const [message, setMessage] = useState("");
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [activeAgent, setActiveAgent] = useState("Supervisor");
  const [busy, setBusy] = useState(false);
  const [approval, setApproval] = useState<{ threadId: string; draft: EmailDraft } | null>(null);
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");
  const [menuOpen, setMenuOpen] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const entryId = useRef(0);

  useEffect(() => {
    const id = window.crypto.randomUUID();
    setThreadId(id);
    fetch(`${API_URL}/health`)
      .then((response) => setApiStatus(response.ok ? "online" : "offline"))
      .catch(() => setApiStatus("offline"));
  }, []);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [entries, approval]);

  function addEntry(entry: Omit<ChatEntry, "id">) {
    entryId.current += 1;
    setEntries((current) => [...current, { ...entry, id: entryId.current }]);
  }

  async function sendMessage(event?: FormEvent<HTMLFormElement>, preset?: string) {
    event?.preventDefault();
    const content = (preset ?? message).trim();
    if (!content || busy || !threadId) return;
    setMessage("");
    setBusy(true);
    setApproval(null);
    addEntry({ role: "user", text: content });
    setActiveAgent("Supervisor");

    try {
      const response = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: content, thread_id: threadId }),
      });
      if (!response.ok || !response.body) throw new Error(`Agent service returned ${response.status}.`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const data = frame.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
          if (data) handleStreamEvent(JSON.parse(data) as StreamEvent);
        }
        if (done) break;
      }
    } catch (error) {
      addEntry({ role: "agent", agent: "System", text: error instanceof Error ? error.message : "Could not reach the local agent." });
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  function handleStreamEvent(event: StreamEvent) {
    setActiveAgent(event.agent);
    if (event.type === "approval_required" && typeof event.content === "object") {
      setApproval({ threadId: event.thread_id, draft: event.content as EmailDraft });
      return;
    }
    if (event.type === "tool_call") {
      addEntry({ role: "activity", agent: event.agent, text: "Using a local tool" });
      return;
    }
    if (event.type === "tool_result") {
      let result = String(event.content);
      try {
        result = JSON.stringify(JSON.parse(result), null, 2);
      } catch {
        // Keep the original tool result when it is not JSON.
      }
      addEntry({ role: "activity", agent: event.agent, text: result });
      return;
    }
    addEntry({ role: "agent", agent: event.agent, text: String(event.content) });
  }

  async function decideApproval(approved: boolean) {
    if (!approval || approvalBusy) return;
    setApprovalBusy(true);
    try {
      const response = await fetch(`${API_URL}/api/approvals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: approval.threadId, approved }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Approval could not be processed.");
      addEntry({ role: "agent", agent: "Email Drafting Subagent", text: result.message });
      setApproval(null);
    } catch (error) {
      addEntry({ role: "agent", agent: "System", text: error instanceof Error ? error.message : "Approval failed." });
    } finally {
      setApprovalBusy(false);
    }
  }

  return (
    <main className="workspace-shell">
      <aside className={`sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Command size={19} strokeWidth={2.2} /></div>
          <div><span className="brand-name">fieldnote</span><span className="brand-subtitle">PRIVATE WORKSPACE</span></div>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={18} /></button>
        </div>

        <div className="workspace-switcher">
          <div className="workspace-avatar">H</div>
          <div className="workspace-name"><strong>Hawthorne & Finch</strong><span>Business workspace</span></div>
          <ArrowDown size={15} className="muted-icon" />
        </div>

        <div className="sidebar-section-label">WORKSPACE</div>
        <nav className="primary-nav" aria-label="Workspace">
          <button className="nav-item nav-item-active"><MessageSquareText size={17} /><span>Assistant</span><span className="nav-shortcut">⌘ 1</span></button>
          <button className="nav-item" onClick={() => setMenuOpen(false)}><Users size={17} /><span>People & agents</span><span className="nav-count">3</span></button>
          <button className="nav-item" onClick={() => setMenuOpen(false)}><FileText size={17} /><span>Firm records</span></button>
        </nav>

        <div className="sidebar-section-heading"><span>YOUR AGENTS</span><button className="tiny-icon-button" aria-label="Add agent" title="Add agent"><Plus size={15} /></button></div>
        <div className="agent-nav-list">
          {specialists.map(({ name, detail, icon: Icon }) => (
            <button className="agent-nav-item" key={name}>
              <span className="agent-nav-icon"><Icon size={15} /></span>
              <span className="agent-nav-copy"><strong>{name}</strong><small>{detail}</small></span>
              <span className="agent-presence" />
            </button>
          ))}
        </div>

        <div className="sidebar-spacer" />
        <div className="privacy-note"><ShieldCheck size={17} /><span><strong>Local by design</strong><small>Records stay on this device</small></span><CheckCircle2 size={15} className="privacy-check" /></div>
        <div className="profile-row"><div className="profile-avatar">HF</div><div><strong>Harper Finch</strong><small>Administrator</small></div><button className="tiny-icon-button" aria-label="Profile options"><ArrowDown size={15} /></button></div>
      </aside>

      <section className="main-column">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Command size={18} /></button>
          <div className="breadcrumb"><span>Workspace</span><span className="crumb-divider">/</span><strong>Assistant</strong></div>
          <div className="topbar-right"><span className={`connection-indicator connection-${apiStatus}`}><i />{apiStatus === "online" ? "LOCAL SYSTEM ONLINE" : apiStatus === "checking" ? "CHECKING LOCAL SYSTEM" : "LOCAL SYSTEM OFFLINE"}</span><button className="icon-button top-activity" aria-label="Activity"><Activity size={18} /></button></div>
        </header>

        <div className="chat-workspace">
          <div className="chat-column">
            <div className="chat-heading">
              <div><div className="eyebrow"><span className="eyebrow-dot" /> FIRM ASSISTANT <span className="heading-divider">/</span> PRIVATE SESSION</div><h1>Good morning, Harper<span className="heading-period">.</span></h1><p>Your firm, in the loop.</p></div>
              <button className="new-chat-button" onClick={() => { setEntries([]); setApproval(null); setThreadId(window.crypto.randomUUID()); }}><Plus size={16} /><span>New chat</span></button>
            </div>

            <div className={`transcript ${entries.length ? "transcript-active" : ""}`} ref={transcriptRef} aria-live="polite">
              {entries.length === 0 ? (
                <div className="empty-state">
                  <div className="empty-icon"><Sparkles size={21} /></div>
                  <h2>What needs your attention?</h2>
                  <p>Start with a record, a clause, or a client follow-up.</p>
                  <div className="suggestion-list">
                    {suggestions.map(({ icon: Icon, text }, index) => <button className="suggestion" key={text} onClick={() => sendMessage(undefined, text)} style={{ animationDelay: `${index * 80}ms` }}><Icon size={16} /><span>{text}</span><ArrowUp size={14} className="suggestion-arrow" /></button>)}
                  </div>
                </div>
              ) : (
                <div className="message-list">
                  {entries.map((entry) => entry.role === "user" ? (
                    <div className="message-row user-row" key={entry.id}><div className="user-message">{entry.text}</div></div>
                  ) : entry.role === "activity" ? (
                    <div className="activity-entry" key={entry.id}><span className="activity-line" /><div><span className="activity-label"><CheckCircle2 size={13} /> {entry.agent} · local lookup</span><pre>{entry.text}</pre></div></div>
                  ) : (
                    <div className="message-row agent-row" key={entry.id}><div className="agent-message-mark"><Command size={15} /></div><div className="agent-message-content"><span className="message-agent-name">{entry.agent ?? "Assistant"}</span><p>{entry.text}</p></div></div>
                  ))}
                  {busy && <div className="working-row"><LoaderCircle size={15} className="spin" /><span>{activeAgent} is working</span><span className="working-pulse" /></div>}
                </div>
              )}

              {approval && (
                <div className="approval-card" role="dialog" aria-label="Review email draft">
                  <div className="approval-topline"><span className="approval-icon"><Mail size={16} /></span><div><strong>Review before sending</strong><small>EMAIL ACTION · HUMAN APPROVAL REQUIRED</small></div><span className="approval-pending"><Circle size={8} /> Pending</span></div>
                  <div className="draft-fields"><div><span>TO</span><strong>{approval.draft.to}</strong></div><div><span>SUBJECT</span><strong>{approval.draft.subject}</strong></div><div className="draft-body"><span>MESSAGE</span><p>{approval.draft.body}</p></div></div>
                  <div className="approval-actions"><span><LockKeyhole size={13} /> Nothing is sent until approved</span><div><button className="reject-button" disabled={approvalBusy} onClick={() => decideApproval(false)}><X size={15} /> Reject</button><button className="approve-button" disabled={approvalBusy} onClick={() => decideApproval(true)}>{approvalBusy ? <LoaderCircle size={15} className="spin" /> : <Check size={15} />} Approve & send</button></div></div>
                </div>
              )}
            </div>

            <form className="composer" onSubmit={(event) => sendMessage(event)}>
              <textarea ref={inputRef} value={message} onChange={(event) => setMessage(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendMessage(); } }} placeholder="Ask about a client, invoice, or contract..." aria-label="Message your firm assistant" rows={1} disabled={busy || apiStatus === "offline"} />
              <div className="composer-footer"><span><span className="composer-lock"><LockKeyhole size={12} /></span> PRIVATE · LOCAL MODEL</span><button className="send-button" aria-label="Send message" type="submit" disabled={!message.trim() || busy || !threadId}><ArrowUp size={17} /></button></div>
            </form>
            <div className="composer-footnote">AI responses can be inaccurate. Verify important records before acting.</div>
          </div>

          <aside className="context-panel">
            <div className="context-header"><span>SESSION CONTEXT</span><button className="tiny-icon-button" aria-label="Context options"><Plus size={15} /></button></div>
            <div className="session-status"><div className="session-status-mark"><Activity size={17} /></div><div><strong>{busy ? "Working on your request" : approval ? "Approval needed" : "Ready when you are"}</strong><small>{busy ? activeAgent : approval ? "Email draft is waiting" : "Your private workspace"}</small></div></div>
            <div className="context-rule" />
            <div className="context-label">AVAILABLE AGENTS <span>03</span></div>
            <div className="context-agent-list">
              {specialists.map(({ name, detail, icon: Icon }) => <div className="context-agent" key={name}><div className="context-agent-icon"><Icon size={16} /></div><div><strong>{name}</strong><small>{detail}</small></div><span className="context-ready"><i /> Ready</span></div>)}
            </div>
            <div className="context-rule" />
            <div className="context-label">SESSION SECURITY</div>
            <div className="security-row"><LockKeyhole size={15} /><span>Model inference</span><strong>On device</strong></div>
            <div className="security-row"><ShieldCheck size={15} /><span>Data handling</span><strong>No cloud</strong></div>
            <div className="security-row"><Users size={15} /><span>Session ID</span><strong className="session-id">{threadId ? threadId.slice(0, 8) : "--------"}</strong></div>
            <div className="context-foot"><span className={`foot-status foot-${apiStatus}`} /><span>{apiStatus === "online" ? "Connected to local runtime" : apiStatus === "checking" ? "Checking runtime" : "Runtime not detected"}</span></div>
          </aside>
        </div>
      </section>
    </main>
  );
}