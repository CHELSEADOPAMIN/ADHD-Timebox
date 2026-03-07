"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/app/utils/api";
import { toStoreTask } from "@/app/utils/taskAdapter";
import { useAppStore, type ChatMessage } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { LogoMark } from "./logo-mark";

const createMessage = (
  role: ChatMessage["role"],
  content: string
): ChatMessage => ({
  id: crypto.randomUUID(),
  role,
  content,
  timestamp: new Date(),
  channel: "planning",
});

export function PlanningMode() {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    planningMessages,
    addPlanningMessage,
    setTasks,
    clearPlanningMessages,
  } = useAppStore();

  // ✅ IME 处理：避免 Enter 结束组词时直接触发发送
  const [isComposing, setIsComposing] = useState(false);
  const lastCompositionEndRef = useRef(0);
  const shouldBlockEnterSend = () => Date.now() - lastCompositionEndRef.current < 80;

  useEffect(() => {
    // Always start with a clean chat on mount (no history across devices).
    clearPlanningMessages();
  }, [clearPlanningMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [planningMessages, isLoading]);

  const getChatErrorMessage = (error: unknown) => {
    if (error instanceof Error) {
      const raw = error.message || "";
      if (
        /failed to fetch|networkerror|err_connection_refused/i.test(raw)
      ) {
        return "Backend is starting up, please try again in a moment...";
      }
      if (raw) {
        return `Sorry, I encountered an error communicating with the backend. ${raw}`;
      }
    }
    return "Sorry, I encountered an error communicating with the backend.";
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    // ✅ 双保险：IME 组词中 or 刚结束组词的那一下 Enter，不发送
    if (isComposing || shouldBlockEnterSend()) return;

    const messageText = input.trim();
    if (!messageText || isLoading) return;

    setInput("");
    addPlanningMessage(createMessage("user", messageText));
    setIsLoading(true);

    try {
      const response = await api.chat(messageText);
      const assistantText = response.ascii_art
        ? [response.content, response.ascii_art].filter(Boolean).join("\n\n")
        : response.content;

      addPlanningMessage(
        createMessage("assistant", assistantText || "(No response)")
      );

      if (response.tasks_updated) {
        try {
          const backendTasks = await api.getTasks();
          setTasks(backendTasks.map(toStoreTask));
        } catch (error) {
          console.error("Failed to refresh tasks", error);
        }
      }
    } catch (error) {
      console.error("Chat error:", error);
      addPlanningMessage(
        createMessage(
          "assistant",
          getChatErrorMessage(error)
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col">
      {/* Chat messages */}
      <div className="flex-1 space-y-4 pb-4">
        {planningMessages.length === 0 && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
              <LogoMark size={28} />
            </div>
            <h2 className="mb-2 text-xl font-medium text-foreground">
              What would you like to work on?
            </h2>
            <p className="max-w-sm text-muted-foreground">
              Tell me what's on your mind. I'll help you turn it into something
              doable.
            </p>
          </div>
        )}

        {planningMessages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex",
              message.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-2xl px-4 py-3",
                message.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-card border border-border text-card-foreground"
              )}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {message.content}
              </p>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-border bg-card px-4 py-3">
              <div className="flex gap-1">
                <span
                  className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground/40"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="border-t border-border pt-4">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What's on your mind?"
            className="min-h-[52px] max-h-32 resize-none"
            disabled={isLoading}
            onCompositionStart={() => {
              setIsComposing(true);
            }}
            onCompositionEnd={(e) => {
              lastCompositionEndRef.current = Date.now();
              setIsComposing(false);
              setInput(e.currentTarget.value);
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;

              // Shift+Enter: 换行
              if (e.shiftKey) return;

              // ✅ 原生 isComposing + 我们的状态 + 刚结束窗口期：都拦住
              // @ts-ignore
              const nativeIsComposing = e.nativeEvent?.isComposing === true;

              if (nativeIsComposing || isComposing || shouldBlockEnterSend()) {
                return; // 让 IME 自己处理 Enter（确认候选/结束组词）
              }

              // 否则 Enter 发送
              e.preventDefault();
              e.stopPropagation();
              handleSubmit(e);
            }}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || isLoading}
            className="h-[52px] w-[52px]"
          >
            <Send className="h-5 w-5" />
            <span className="sr-only">Send message</span>
          </Button>
        </form>
      </div>
    </div>
  );
}
