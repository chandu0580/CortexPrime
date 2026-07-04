"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { usePathname } from "next/navigation";
import {
  Activity,
  Archive,
  BarChart2,
  Bell,
  Bot,
  Brain,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Filter,
  Globe,
  Home,
  Mic,
  Monitor,
  MoreVertical,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Send,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
  Paperclip,
  FileText,
  BarChart,
  MessageSquare,
  Users,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";

// ─── NAV ──────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home     },
  { href: "/runtime",       label: "Runtime",      icon: Zap      },
  { href: "/agents",        label: "Agents",       icon: Bot      },
  { href: "/missions",      label: "Missions",     icon: Target   },
  { href: "/chat",          label: "Chat",         icon: MessageSquare },
  { href: "/memory",        label: "Memory",       icon: Brain    },
  { href: "/workspace",     label: "Research",     icon: Search   },
  { href: "/operator",      label: "Computer Use", icon: Monitor  },
  { href: "/operator",      label: "Browser",      icon: Globe    },
  { href: "/replay",        label: "Replay",       icon: Archive  },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2 },
  { href: "/governance",    label: "Governance",   icon: Shield   },
  { href: "/system-status", label: "Monitoring",   icon: Activity },
  { href: "/integrations",  label: "Integrations", icon: Puzzle   },
  { href: "/settings",      label: "Settings",     icon: Settings },
];

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  const pathname = usePathname();
  return (
    <aside className={cn(
      "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#EAEFF5] bg-white transition-all duration-300",
      collapsed ? "w-[68px]" : "w-[220px]"
    )}>
      <div className={cn("flex items-center gap-2.5 px-4 py-5", collapsed && "justify-center px-0")}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-5 w-5 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round"/>
            <path d="M24 13 31 17v14l-7 4-7-4V17l7-4Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round"/>
          </svg>
        </div>
        {!collapsed && (
          <div>
            <p className="text-[0.95rem] font-bold leading-tight tracking-[-0.03em] text-[#111827]">CortexPrime</p>
            <p className="text-[0.68rem] font-medium text-[#9CA3AF]">AI Operating System</p>
          </div>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== "/" && !href.includes("#") && pathname.startsWith(href));
          return (
            <Link key={label} href={href} className={cn(
              "flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 transition-all",
              isActive ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]",
              collapsed && "justify-center px-0"
            )}>
              <Icon className="h-4 w-4 shrink-0"/>
              {!collapsed && <span className="text-[0.875rem] font-semibold">{label}</span>}
              {!collapsed && isActive && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-[#38B88A]"/>}
            </Link>
          );
        })}
      </nav>
      <div className={cn("px-2 pb-4 space-y-2", collapsed && "px-1")}>
        {!collapsed && (
          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-2.5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]"/>
              <div className="flex-1 min-w-0">
                <p className="text-[0.72rem] font-semibold text-[#2F9F77]">System Status</p>
                <p className="text-[0.7rem] font-bold text-[#38B88A]">Healthy</p>
                <p className="text-[0.66rem] text-[#9CA3AF]">All systems operational</p>
              </div>
              <RefreshCw className="h-3.5 w-3.5 text-[#D1D5DB] cursor-pointer hover:text-[#38B88A]"/>
            </div>
          </div>
        )}
        <button onClick={onCollapse} className={cn(
          "flex w-full items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.82rem] font-semibold text-[#6B7280] transition hover:bg-[#F8FAFC]",
          collapsed && "justify-center"
        )}>
          {collapsed ? <ChevronRight className="h-4 w-4"/> : <><ChevronLeft className="h-4 w-4"/><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ collapsed }: { collapsed: boolean }) {
  const avatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, []);
  return (
    <header className={cn(
      "sticky top-0 z-30 flex items-center gap-3 border-b border-[#EAEFF5] bg-white/96 px-5 py-3 backdrop-blur transition-all duration-300",
      collapsed ? "pl-[80px]" : "pl-[232px]"
    )}>
      <label className="relative flex h-10 w-[240px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#9CA3AF]"/>
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] pl-10 pr-14 text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"/>
        <span className="absolute right-3 rounded-[7px] border border-[#E5E7EB] bg-white px-1.5 py-0.5 text-[0.66rem] font-semibold text-[#9CA3AF]">⌘K</span>
      </label>
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 xl:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Target className="h-3.5 w-3.5"/></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-2">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.6rem] font-bold text-[#2F9F77]"><span className="h-1 w-1 rounded-full bg-[#38B88A]"/>Running</span>
          </div>
        </div>
        <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] ml-1"/>
      </div>
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 lg:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Mic className="h-3.5 w-3.5"/></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.8rem] font-semibold text-[#111827]">Not Active</p>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button className="relative flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
          <Bell className="h-4 w-4"/>
          <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#EF4444] text-[0.68rem] font-bold text-white ring-2 ring-white">3</span>
        </button>
        <div className="flex items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-white p-1 pr-3 hover:bg-[#F8FAFC] cursor-pointer">
          <Image src={avatar} alt="Alex Morgan" width={32} height={32} className="rounded-[10px]"/>
          <div className="leading-tight text-left hidden sm:block">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.68rem] font-medium text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] hidden sm:block"/>
        </div>
      </div>
    </header>
  );
}

// ─── Data ─────────────────────────────────────────────────────────────────────
const conversations = [
  { id: 1, title: "Market Intelligence Report", subtitle: "Analyze the Q2 market trends for AI...", time: "3m ago", active: true },
  { id: 2, title: "Competitor Analysis", subtitle: "Compare our product features with competitors...", time: "18m ago", active: false },
  { id: 3, title: "Revenue Forecast", subtitle: "Generate predictions for next quarter...", time: "1h ago", active: false },
  { id: 4, title: "Product Roadmap", subtitle: "Suggest key features for upcoming releases...", time: "2h ago", active: false },
  { id: 5, title: "Customer Feedback Summary", subtitle: "Summarize the feedback from last month...", time: "3h ago", active: false },
  { id: 6, title: "Pricing Strategy", subtitle: "Help optimize our pricing strategies...", time: "5h ago", active: false },
];

const aiAgents = [
  { name: "Research Agent", status: "Online", color: "bg-[#38B88A]" },
  { name: "Data Analyst", status: "Online", color: "bg-[#38B88A]" },
  { name: "Market Analyst", status: "Online", color: "bg-[#38B88A]" },
  { name: "Report Generator", status: "Online", color: "bg-[#38B88A]" },
  { name: "Insight Finder", status: "Online", color: "bg-[#38B88A]" },
  { name: "Competitor Scout", status: "Online", color: "bg-[#38B88A]" },
];

const quickActions = [
  { label: "Generate Report", icon: FileText },
  { label: "Analyze Data", icon: BarChart },
  { label: "Summarize", icon: MessageSquare },
  { label: "Get Insights", icon: Sparkles },
];

const initialMessages = [
  {
    id: 1,
    role: "user",
    content: "Analyze the Q2 market trends for AI automation tools and provide key insights.",
    time: "10:30 AM",
  },
  {
    id: 2,
    role: "assistant",
    content: `Here's an analysis of Q2 market trends for AI automation tools:

**Market Growth:** The AI automation tools market grew by 28.5% in Q2 2024.

- **Key Drivers:** Increased adoption in enterprise, cost reduction needs, and productivity gains.
- **Top Trends:** Workflow automation, AI agents, and no-code platforms dominate.
- **Leading Players:** Microsoft, UiPath, Automation Anywhere, and Zapier lead the market.
- **Outlook:** Strong growth expected to continue in Q3 and Q4.

Would you like me to generate a report with charts and data?`,
    time: "10:30 AM",
  },
];

// ─── Markdown-like renderer ────────────────────────────────────────────────────
function MessageContent({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="space-y-1.5 text-[0.82rem] leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith("**") && line.endsWith("**")) {
          return <p key={i} className="font-bold text-[#111827]">{line.slice(2, -2)}</p>;
        }
        if (line.startsWith("- **")) {
          const parts = line.slice(2).split(":** ");
          return (
            <div key={i} className="flex gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#38B88A] shrink-0"/>
              <p><span className="font-bold text-[#111827]">{parts[0].replace("**", "").replace("**", "")}</span>
                {parts[1] ? `: ${parts[1]}` : ""}</p>
            </div>
          );
        }
        if (line.trim() === "") return <div key={i} className="h-1"/>;
        return <p key={i}>{line}</p>;
      })}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function ChatPage() {
  const [collapsed, setCollapsed] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(true);
  const [selectedConv, setSelectedConv] = useState(conversations[0]);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    const userMsg = { id: messages.length + 1, role: "user", content: input, time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setIsTyping(true);
    setTimeout(() => {
      setMessages(prev => [...prev, {
        id: prev.length + 1,
        role: "assistant",
        content: "I'm analyzing your request and gathering relevant data from our knowledge base. I'll have a comprehensive response for you shortly with the latest insights.",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      }]);
      setIsTyping(false);
    }, 1500);
  };

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed(v => !v)}/>
      <div className={cn("flex min-h-screen flex-col transition-all duration-300", collapsed ? "pl-[68px]" : "pl-[220px]")}>
        <Header collapsed={collapsed}/>

        {/* 3-column chat layout */}
        <div className="flex flex-1 overflow-hidden" style={{ height: "calc(100vh - 57px)" }}>

          {/* Left: Conversation History — ChatGPT-style toggle */}
          <AnimatePresence initial={false}>
            {historyOpen && (
              <motion.div
                key="history-panel"
                initial={{ width: 0, opacity: 0 }}
                animate={{ width: 280, opacity: 1 }}
                exit={{ width: 0, opacity: 0 }}
                transition={{ duration: 0.25, ease: "easeInOut" }}
                className="shrink-0 border-r border-[#EAEFF5] bg-white flex flex-col overflow-hidden"
                style={{ minWidth: 0 }}
              >
                <div className="p-4 border-b border-[#EAEFF5]">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-[0.9rem] font-bold text-[#111827] whitespace-nowrap">AI Chat Assistant</h2>
                    <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-[#F8FAFC] text-[#38B88A] hover:bg-[#ECFBF4] transition-colors shrink-0">
                      <Plus className="h-4 w-4"/>
                    </button>
                  </div>
                  <p className="text-[0.74rem] text-[#9CA3AF]">Chat with your AI agents and get intelligent responses.</p>
                </div>

                <div className="flex-1 overflow-y-auto">
                  <div className="flex items-center justify-between px-4 py-2.5">
                    <span className="text-[0.7rem] font-bold uppercase tracking-wider text-[#9CA3AF]">+ New Chat</span>
                  </div>
                  {conversations.map(conv => (
                    <button
                      key={conv.id}
                      onClick={() => setSelectedConv(conv)}
                      className={cn(
                        "w-full text-left px-4 py-3 border-b border-[#F8FAFC] transition-all",
                        selectedConv.id === conv.id ? "bg-[#F4F7FA]" : "hover:bg-[#F8FAFC]"
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[0.8rem] font-bold text-[#111827] truncate">{conv.title}</p>
                        <span className="text-[0.66rem] text-[#9CA3AF] shrink-0">{conv.time}</span>
                      </div>
                      <p className="mt-0.5 text-[0.72rem] text-[#9CA3AF] truncate">{conv.subtitle}</p>
                    </button>
                  ))}
                </div>

                <div className="p-4 border-t border-[#EAEFF5]">
                  <button className="w-full rounded-[12px] border border-[#EAEFF5] py-2 text-[0.76rem] font-bold text-[#6B7280] hover:bg-[#F8FAFC] whitespace-nowrap">
                    View All Conversations
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Center: Chat */}
          <div className="flex-1 flex flex-col min-w-0 bg-[#F4F7FA]">
            {/* Chat header */}
            <div className="bg-white border-b border-[#EAEFF5] px-4 py-3 flex items-center gap-3 justify-between">
              {/* Toggle history sidebar button */}
              <button
                onClick={() => setHistoryOpen(v => !v)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border border-[#EAEFF5] bg-[#F8FAFC] text-[#6B7280] hover:bg-[#ECFBF4] hover:text-[#2F9F77] hover:border-[#D6F0E5] transition-all"
                title={historyOpen ? "Close chat history" : "Open chat history"}
              >
                {historyOpen
                  ? <PanelLeftClose className="h-4 w-4"/>
                  : <PanelLeftOpen className="h-4 w-4"/>
                }
              </button>
              <div className="flex-1 min-w-0">
                <h3 className="text-[0.9rem] font-bold text-[#111827] truncate">{selectedConv.title}</h3>
                <p className="text-[0.72rem] text-[#9CA3AF] truncate">{selectedConv.subtitle}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFBF4] px-2.5 py-1 text-[0.72rem] font-bold text-[#2F9F77]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] animate-pulse"/>Market Intelligence Report
                </span>

              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-5">
              {messages.map(msg => (
                <div key={msg.id} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>
                  {msg.role === "assistant" && (
                    <div className="h-9 w-9 rounded-full bg-[#38B88A] flex items-center justify-center shrink-0">
                      <Bot className="h-5 w-5 text-white"/>
                    </div>
                  )}
                  <div className={cn(
                    "max-w-[75%] rounded-[16px] px-4 py-3",
                    msg.role === "user"
                      ? "bg-[#38B88A] text-white rounded-tr-[4px]"
                      : "bg-white border border-[#EAEFF5] text-[#374151] rounded-tl-[4px] shadow-[0_2px_8px_rgba(148,163,184,0.06)]"
                  )}>
                    {msg.role === "user" ? (
                      <p className="text-[0.82rem] leading-relaxed font-semibold">{msg.content}</p>
                    ) : (
                      <MessageContent content={msg.content}/>
                    )}
                    <p className={cn("mt-2 text-[0.66rem]", msg.role === "user" ? "text-white/70" : "text-[#9CA3AF]")}>{msg.time}</p>
                  </div>
                  {msg.role === "user" && (
                    <div className="h-9 w-9 rounded-full bg-[#ECFBF4] flex items-center justify-center shrink-0 text-[0.75rem] font-bold text-[#38B88A]">
                      AM
                    </div>
                  )}
                </div>
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <div className="flex gap-3 justify-start">
                  <div className="h-9 w-9 rounded-full bg-[#38B88A] flex items-center justify-center shrink-0">
                    <Bot className="h-5 w-5 text-white"/>
                  </div>
                  <div className="bg-white border border-[#EAEFF5] rounded-[16px] rounded-tl-[4px] px-4 py-3 shadow-[0_2px_8px_rgba(148,163,184,0.06)]">
                    <div className="flex items-center gap-1.5">
                      {[0, 1, 2].map(i => (
                        <motion.div key={i} className="h-2 w-2 rounded-full bg-[#38B88A]"
                          animate={{ y: [-2, 2, -2] }}
                          transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }}/>
                      ))}
                    </div>
                  </div>
                </div>
              )}
              <div ref={endRef}/>
            </div>

            {/* Input area */}
            <div className="bg-white border-t border-[#EAEFF5] p-4">
              <div className="flex items-end gap-3 rounded-[16px] border border-[#EAEFF5] bg-[#F8FAFC] px-4 py-3">
                <textarea
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Message AI assistant..."
                  className="flex-1 resize-none bg-transparent text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] max-h-24 min-h-[24px]"
                  rows={1}
                />
                <div className="flex items-center gap-2 shrink-0">
                  <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#9CA3AF] hover:text-[#374151]">
                    <Paperclip className="h-4 w-4"/>
                  </button>
                  <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#9CA3AF] hover:text-[#374151]">
                    <Settings className="h-4 w-4"/>
                  </button>
                  <button
                    onClick={handleSend}
                    disabled={!input.trim()}
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-[8px] transition-all",
                      input.trim() ? "bg-[#38B88A] text-white shadow-[0_4px_8px_rgba(56,184,138,0.3)]" : "bg-[#E5E7EB] text-[#9CA3AF]"
                    )}
                  >
                    <Send className="h-4 w-4"/>
                  </button>
                </div>
              </div>
              <p className="mt-2 text-center text-[0.66rem] text-[#9CA3AF]">AI responses can be inaccurate. Please verify important information.</p>
            </div>
          </div>

          {/* Right: AI Agents + Quick Actions */}
          <div className="w-[260px] shrink-0 border-l border-[#EAEFF5] bg-white flex flex-col">

            {/* AI Agents section */}
            <div className="p-4 border-b border-[#EAEFF5] flex-1">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-[0.88rem] font-bold text-[#111827]">AI Agents</h3>
              </div>
              <div className="space-y-2">
                {aiAgents.map((agent, idx) => (
                  <div key={idx} className="flex items-center justify-between rounded-[10px] p-2.5 hover:bg-[#F8FAFC] cursor-pointer transition-all">
                    <div className="flex items-center gap-2.5">
                      <div className="h-7 w-7 rounded-[8px] bg-[#ECFBF4] flex items-center justify-center">
                        <Bot className="h-3.5 w-3.5 text-[#38B88A]"/>
                      </div>
                      <span className="text-[0.78rem] font-semibold text-[#111827]">{agent.name}</span>
                    </div>
                    <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.62rem] font-bold text-[#2F9F77]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]"/>
                      Online
                    </span>
                  </div>
                ))}
              </div>
              <button className="mt-3 w-full rounded-[10px] border border-[#EAEFF5] py-2 text-[0.74rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                Manage Agents
              </button>
            </div>

            {/* Quick Actions section */}
            <div className="p-4">
              <h3 className="text-[0.88rem] font-bold text-[#111827] mb-3">Quick Actions</h3>
              <div className="grid grid-cols-2 gap-2">
                {quickActions.map((action, idx) => {
                  const Icon = action.icon;
                  return (
                    <button
                      key={idx}
                      className="flex items-center gap-2 rounded-[10px] border border-[#EAEFF5] bg-[#F8FAFC] p-2.5 text-left text-[0.72rem] font-bold text-[#374151] hover:bg-[#ECFBF4] hover:text-[#2F9F77] hover:border-[#D6F0E5] transition-all"
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0"/>
                      {action.label}
                    </button>
                  );
                })}
              </div>
            </div>

          </div>
        </div>

        {/* Footer */}
        <div className={cn("border-t border-[#EAEFF5] bg-white px-5 py-2 flex items-center justify-between text-[0.72rem] text-[#9CA3AF] transition-all duration-300", collapsed ? "pl-[80px]" : "pl-[232px]")}>
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-3 w-3 text-[#38B88A]"/>
            <span>Enterprise Secure</span>
            <span>• SOC 2 Type II</span>
            <span>• GDPR Compliant</span>
          </div>
          <p>© 2026 CortexPrime. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}
