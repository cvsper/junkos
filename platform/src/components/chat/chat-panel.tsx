"use client";

import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type FormEvent,
} from "react";
import { io, type Socket } from "socket.io-client";
import { X, Send, MessageCircle, Check, CheckCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { chatApi, type ChatMessageRecord } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatPanelProps {
  jobId: string;
  isOpen: boolean;
  onClose: () => void;
  /** The role of the current user: customer or driver */
  userRole: "customer" | "driver";
}

// ---------------------------------------------------------------------------
// Socket singleton
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

let _socket: Socket | null = null;

function getSocket(): Socket {
  if (!_socket) {
    _socket = io(API_BASE_URL, {
      transports: ["websocket", "polling"],
      autoConnect: false,
    });
  }
  return _socket;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ChatPanel({ jobId, isOpen, onClose, userRole }: ChatPanelProps) {
  const { user } = useAuthStore();

  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [otherTyping, setOtherTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const typingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevOpenRef = useRef(false);

  // ------- Scroll to bottom -------
  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    requestAnimationFrame(() => {
      messagesEndRef.current?.scrollIntoView({ behavior });
    });
  }, []);

  // ------- Fetch messages via REST -------
  const fetchMessages = useCallback(
    async (before?: string) => {
      try {
        const res = await chatApi.getMessages(jobId, before, 50);
        if (before) {
          // Prepend older messages
          setMessages((prev) => [...res.messages, ...prev]);
        } else {
          setMessages(res.messages);
        }
        setHasMore(res.has_more);
      } catch {
        setError("Failed to load messages");
      } finally {
        setIsLoading(false);
      }
    },
    [jobId]
  );

  // ------- Mark messages as read -------
  const markRead = useCallback(() => {
    chatApi.markRead(jobId).catch(() => {});
    // Also notify via socket
    const socket = getSocket();
    if (socket.connected) {
      socket.emit("chat:read", { job_id: jobId, reader_role: userRole });
    }
  }, [jobId, userRole]);

  // ------- Socket setup -------
  useEffect(() => {
    if (!isOpen) return;

    const socket = getSocket();

    function onConnect() {
      setIsConnected(true);
      // Join the job room
      socket.emit("join", { room: jobId });
      // Stop REST polling when socket connects
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }

    function onDisconnect() {
      setIsConnected(false);
      // Start REST polling as fallback
      if (!pollingRef.current) {
        pollingRef.current = setInterval(() => {
          fetchMessages();
        }, 5000);
      }
    }

    function onChatMessage(msg: ChatMessageRecord) {
      setMessages((prev) => {
        // Deduplicate by id
        if (prev.some((m) => m.id === msg.id)) return prev;
        return [...prev, msg];
      });
      // If the new message is from the other party, mark as read
      if (msg.sender_role !== userRole) {
        markRead();
      }
      setOtherTyping(false);
    }

    function onChatTyping(data: {
      sender_role: string;
      is_typing: boolean;
    }) {
      if (data.sender_role !== userRole) {
        setOtherTyping(data.is_typing);
      }
    }

    function onChatRead(data: {
      read_by: string;
      read_at: string;
    }) {
      // If the other party read our messages, update read_at
      if (data.read_by !== userRole) {
        setMessages((prev) =>
          prev.map((m) =>
            m.sender_role === userRole && !m.read_at
              ? { ...m, read_at: data.read_at }
              : m
          )
        );
      }
    }

    socket.on("connect", onConnect);
    socket.on("disconnect", onDisconnect);
    socket.on("chat:message", onChatMessage);
    socket.on("chat:typing", onChatTyping);
    socket.on("chat:read", onChatRead);

    if (!socket.connected) {
      socket.connect();
    } else {
      onConnect();
    }

    return () => {
      socket.off("connect", onConnect);
      socket.off("disconnect", onDisconnect);
      socket.off("chat:message", onChatMessage);
      socket.off("chat:typing", onChatTyping);
      socket.off("chat:read", onChatRead);
      socket.emit("leave", { room: jobId });
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [isOpen, jobId, userRole, fetchMessages, markRead]);

  // ------- Initial fetch when opening -------
  useEffect(() => {
    if (isOpen && !prevOpenRef.current) {
      setIsLoading(true);
      setError(null);
      fetchMessages();
    }
    prevOpenRef.current = isOpen;
  }, [isOpen, fetchMessages]);

  // ------- Scroll to bottom on new messages -------
  useEffect(() => {
    if (isOpen && messages.length > 0) {
      scrollToBottom();
    }
  }, [messages.length, isOpen, scrollToBottom]);

  // ------- Focus input when panel opens -------
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 300);
      // Mark existing messages as read
      markRead();
    }
  }, [isOpen, markRead]);

  // ------- Send message -------
  const handleSend = async (e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || isSending) return;

    setInput("");
    setIsSending(true);

    // Optimistic update
    const optimisticMsg: ChatMessageRecord = {
      id: `temp-${Date.now()}`,
      job_id: jobId,
      sender_id: user?.id || "",
      sender_role: userRole,
      message: text,
      read_at: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMsg]);

    try {
      const socket = getSocket();
      if (socket.connected) {
        // Send via socket for real-time delivery
        socket.emit("chat:send", {
          job_id: jobId,
          sender_id: user?.id,
          sender_role: userRole,
          message: text,
        });
      } else {
        // Fallback to REST
        const res = await chatApi.sendMessage(jobId, text);
        // Replace optimistic message with real one
        setMessages((prev) =>
          prev.map((m) =>
            m.id === optimisticMsg.id ? res.message : m
          )
        );
      }
    } catch {
      // Remove optimistic message on failure
      setMessages((prev) =>
        prev.filter((m) => m.id !== optimisticMsg.id)
      );
      setError("Failed to send message");
    } finally {
      setIsSending(false);
    }
  };

  // ------- Typing indicator -------
  const handleInputChange = (value: string) => {
    setInput(value);

    const socket = getSocket();
    if (!socket.connected) return;

    socket.emit("chat:typing", {
      job_id: jobId,
      sender_id: user?.id,
      sender_role: userRole,
      is_typing: true,
    });

    // Clear previous timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    typingTimeoutRef.current = setTimeout(() => {
      socket.emit("chat:typing", {
        job_id: jobId,
        sender_id: user?.id,
        sender_role: userRole,
        is_typing: false,
      });
    }, 2000);
  };

  // ------- Load older messages -------
  const loadMore = () => {
    if (!hasMore || isLoading || messages.length === 0) return;
    fetchMessages(messages[0].id);
  };

  // ------- Time formatting -------
  function formatTime(iso: string): string {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function formatDateSeparator(iso: string): string {
    const d = new Date(iso);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = d.toDateString() === yesterday.toDateString();

    if (isToday) return "Today";
    if (isYesterday) return "Yesterday";
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      month: "short",
      day: "numeric",
    });
  }

  // ------- Check if we need a date separator -------
  function needsDateSeparator(idx: number): boolean {
    if (idx === 0) return true;
    const prev = new Date(messages[idx - 1].created_at).toDateString();
    const curr = new Date(messages[idx].created_at).toDateString();
    return prev !== curr;
  }

  // ------- Render -------
  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm sm:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          "fixed z-50 bg-card border-l border-border shadow-2xl flex flex-col",
          // Mobile: full screen from bottom
          "inset-x-0 bottom-0 top-16 sm:top-auto sm:inset-x-auto",
          // Desktop: right side panel
          "sm:right-0 sm:top-0 sm:bottom-0 sm:w-[420px]",
          // Slide animation
          "transition-transform duration-300 ease-out",
          isOpen
            ? "translate-x-0"
            : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center">
              <MessageCircle className="w-4 h-4 text-primary" />
            </div>
            <div>
              <h3 className="text-sm font-semibold leading-none">
                {userRole === "customer" ? "Chat with Driver" : "Chat with Customer"}
              </h3>
              <p className="text-[11px] text-muted-foreground mt-0.5 flex items-center gap-1.5">
                {isConnected ? (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
                    Connected
                  </>
                ) : (
                  <>
                    <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 inline-block" />
                    Reconnecting...
                  </>
                )}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-muted transition-colors"
            aria-label="Close chat"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages area */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto px-4 py-3 space-y-1 min-h-0"
        >
          {/* Load more button */}
          {hasMore && (
            <div className="text-center py-2">
              <button
                onClick={loadMore}
                className="text-xs text-primary hover:underline"
              >
                Load earlier messages
              </button>
            </div>
          )}

          {/* Loading state */}
          {isLoading && messages.length === 0 && (
            <div className="flex items-center justify-center py-12">
              <svg
                className="h-6 w-6 animate-spin text-primary"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              <span className="ml-2 text-sm text-muted-foreground">
                Loading messages...
              </span>
            </div>
          )}

          {/* Empty state */}
          {!isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-14 h-14 rounded-full bg-muted flex items-center justify-center mb-3">
                <MessageCircle className="w-7 h-7 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium text-foreground">No messages yet</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-[240px]">
                Send a message to start chatting with your{" "}
                {userRole === "customer" ? "driver" : "customer"}.
              </p>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-center mb-2">
              <p className="text-xs text-destructive">{error}</p>
              <button
                onClick={() => {
                  setError(null);
                  fetchMessages();
                }}
                className="text-xs text-primary hover:underline mt-1"
              >
                Retry
              </button>
            </div>
          )}

          {/* Message list */}
          {messages.map((msg, idx) => {
            const isMine = msg.sender_role === userRole;
            const showDateSep = needsDateSeparator(idx);

            return (
              <div key={msg.id}>
                {/* Date separator */}
                {showDateSep && (
                  <div className="flex items-center gap-3 py-3">
                    <div className="flex-1 h-px bg-border" />
                    <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                      {formatDateSeparator(msg.created_at)}
                    </span>
                    <div className="flex-1 h-px bg-border" />
                  </div>
                )}

                {/* Message bubble */}
                <div
                  className={cn(
                    "flex mb-1.5",
                    isMine ? "justify-end" : "justify-start"
                  )}
                >
                  <div className="max-w-[80%]">
                    <div
                      className={cn(
                        "rounded-2xl px-3.5 py-2 text-sm leading-relaxed",
                        isMine
                          ? "bg-primary text-primary-foreground rounded-br-md"
                          : "bg-muted text-foreground rounded-bl-md"
                      )}
                    >
                      {msg.message}
                    </div>
                    {/* Timestamp + read receipt */}
                    <div
                      className={cn(
                        "flex items-center gap-1 mt-0.5 px-1",
                        isMine ? "justify-end" : "justify-start"
                      )}
                    >
                      <span className="text-[10px] text-muted-foreground/60">
                        {formatTime(msg.created_at)}
                      </span>
                      {isMine && (
                        <span className="text-muted-foreground/60">
                          {msg.read_at ? (
                            <CheckCheck className="w-3 h-3 text-primary" />
                          ) : (
                            <Check className="w-3 h-3" />
                          )}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}

          {/* Typing indicator */}
          {otherTyping && (
            <div className="flex justify-start mb-1.5">
              <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-2.5 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <form
          onSubmit={handleSend}
          className="border-t border-border px-3 py-2.5 bg-card"
        >
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              placeholder="Type a message..."
              disabled={isSending}
              maxLength={2000}
              className="flex-1 bg-muted/50 border border-border rounded-full px-4 py-2 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 disabled:opacity-50 transition-colors"
            />
            <button
              type="submit"
              disabled={!input.trim() || isSending}
              className="flex-shrink-0 w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>
    </>
  );
}
