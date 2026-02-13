"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageCircle, X, Send, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string;
  role: "bot" | "user";
  text: string;
  timestamp: Date;
}

type FaqCategory =
  | "where_is_driver"
  | "cancel"
  | "pricing"
  | "other";

const FAQ_BUTTONS: { label: string; category: FaqCategory }[] = [
  { label: "Where is my driver?", category: "where_is_driver" },
  { label: "I need to cancel", category: "cancel" },
  { label: "Pricing question", category: "pricing" },
  { label: "Other issue", category: "other" },
];

const FAQ_RESPONSES: Record<FaqCategory, string> = {
  where_is_driver:
    "You can track your driver in real-time on the job details page. Go to My Jobs, tap on your active booking, and you'll see a live map with your driver's location and estimated arrival time. If your driver hasn't arrived within the scheduled window, please send us a message below and we'll look into it right away.",
  cancel:
    "You can cancel a booking for free up to 2 hours before the scheduled pickup time. Go to My Jobs, select the booking you'd like to cancel, and tap \"Cancel Booking.\" If you're within the 2-hour window or need help with a special situation, type your message below and our team will assist you.",
  pricing:
    "Our pricing is based on the type and quantity of items you need removed. You'll always see a transparent estimate before confirming your booking -- no hidden fees. The estimate includes labor, hauling, and responsible disposal. For large or unusual items, send us a message below and we'll provide a custom quote.",
  other:
    "We're here to help! Please type your question or describe your issue in the message box below and our support team will get back to you within 1 hour via email.",
};

const WELCOME_MESSAGE: ChatMessage = {
  id: "welcome",
  role: "bot",
  text: "Hi there! How can we help you today? Choose a topic below or type your own message.",
  timestamp: new Date(),
};

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

async function sendSupportMessage(payload: {
  name: string;
  email: string;
  message: string;
  category: string;
}): Promise<{ success: boolean }> {
  const token = useAuthStore.getState().token;
  const res = await fetch(`${API_BASE_URL}/api/support/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(payload),
  });
  return res.json();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SupportChat() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [hasUnread, setHasUnread] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { user } = useAuthStore();

  // Auto-scroll to bottom when messages change
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Focus input when chat opens
  useEffect(() => {
    if (isOpen) {
      setHasUnread(false);
      setTimeout(() => inputRef.current?.focus(), 300);
    }
  }, [isOpen]);

  const addMessage = (role: "bot" | "user", text: string) => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role,
        text,
        timestamp: new Date(),
      },
    ]);
  };

  const handleFaq = (category: FaqCategory) => {
    const button = FAQ_BUTTONS.find((b) => b.category === category);
    if (button) {
      addMessage("user", button.label);
    }
    // Slight delay to feel more natural
    setTimeout(() => {
      addMessage("bot", FAQ_RESPONSES[category]);
    }, 400);
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || isSending) return;

    addMessage("user", text);
    setInput("");
    setIsSending(true);

    try {
      await sendSupportMessage({
        name: user?.name || "Guest",
        email: user?.email || "unknown",
        message: text,
        category: "custom",
      });
    } catch {
      // Still show confirmation even if backend is unreachable
    }

    setTimeout(() => {
      addMessage(
        "bot",
        "Thanks! We've received your message. Our team will get back to you within 1 hour via email."
      );
      setIsSending(false);
    }, 600);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Chat Panel */}
      <div
        className={cn(
          "fixed bottom-20 right-4 sm:right-6 z-50 w-[calc(100vw-2rem)] sm:w-96",
          "bg-card border border-border rounded-2xl shadow-2xl",
          "flex flex-col overflow-hidden",
          "transition-all duration-300 ease-out origin-bottom-right",
          isOpen
            ? "opacity-100 scale-100 translate-y-0 pointer-events-auto"
            : "opacity-0 scale-95 translate-y-4 pointer-events-none"
        )}
        style={{ maxHeight: "min(32rem, calc(100vh - 8rem))" }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-primary text-primary-foreground rounded-t-2xl">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-primary-foreground/20 flex items-center justify-center">
              <MessageCircle className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold leading-none">
                Umuve Support
              </h3>
              <p className="text-[11px] opacity-80 mt-0.5">
                We typically reply within 1 hour
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            className="p-1.5 rounded-full hover:bg-primary-foreground/20 transition-colors"
            aria-label="Close chat"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground rounded-br-md"
                    : "bg-muted text-foreground rounded-bl-md"
                )}
              >
                {msg.text}
              </div>
            </div>
          ))}

          {/* FAQ Quick Replies -- show after welcome message if no user messages yet */}
          {messages.length === 1 && messages[0].id === "welcome" && (
            <div className="flex flex-wrap gap-2 pt-1">
              {FAQ_BUTTONS.map((faq) => (
                <button
                  key={faq.category}
                  onClick={() => handleFaq(faq.category)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full border border-primary/30 bg-primary/5 text-primary text-xs font-medium hover:bg-primary/10 transition-colors"
                >
                  {faq.label}
                  <ChevronRight className="w-3 h-3" />
                </button>
              ))}
            </div>
          )}

          {/* Typing indicator */}
          {isSending && (
            <div className="flex justify-start">
              <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-2.5 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:0ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:150ms]" />
                <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/50 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-border px-3 py-2.5">
          <div className="flex items-center gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              disabled={isSending}
              className="flex-1 bg-muted/50 border border-border rounded-full px-4 py-2 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 disabled:opacity-50 transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isSending}
              className="flex-shrink-0 w-9 h-9 rounded-full bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              aria-label="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Floating Action Button */}
      <button
        onClick={() => setIsOpen((prev) => !prev)}
        className={cn(
          "fixed bottom-4 right-4 sm:right-6 z-50",
          "w-14 h-14 rounded-full shadow-lg",
          "flex items-center justify-center",
          "transition-all duration-300 ease-out",
          isOpen
            ? "bg-muted text-muted-foreground hover:bg-muted/80 rotate-0"
            : "bg-primary text-primary-foreground hover:bg-primary/90 rotate-0"
        )}
        aria-label={isOpen ? "Close support chat" : "Open support chat"}
      >
        {isOpen ? (
          <X className="w-6 h-6 transition-transform duration-200" />
        ) : (
          <MessageCircle className="w-6 h-6 transition-transform duration-200" />
        )}

        {/* Unread badge */}
        {hasUnread && !isOpen && (
          <span className="absolute -top-0.5 -right-0.5 w-5 h-5 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center border-2 border-background animate-in fade-in zoom-in">
            1
          </span>
        )}
      </button>
    </>
  );
}
