"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";
import { api } from "@/app/utils/api";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore, type ChatMessage } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Send, ParkingCircle } from "lucide-react";

const createMessage = (
  role: ChatMessage["role"],
  content: string
): ChatMessage => ({
  id: crypto.randomUUID(),
  role,
  content,
  timestamp: new Date(),
  channel: "parking",
});

function PendingIndicator() {
  return (
    <div className="flex justify-start">
      <div
        className="rounded-2xl bg-muted px-4 py-2.5"
        role="status"
        aria-live="polite"
      >
        <div className="flex gap-1">
          <span
            className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce"
            style={{ animationDelay: "0ms" }}
          />
          <span
            className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce"
            style={{ animationDelay: "150ms" }}
          />
          <span
            className="h-2 w-2 rounded-full bg-muted-foreground/40 animate-bounce"
            style={{ animationDelay: "300ms" }}
          />
        </div>
        <span className="sr-only">Assistant is thinking</span>
      </div>
    </div>
  );
}

export function ThoughtParkingSheet() {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const {
    showThoughtParking,
    setShowThoughtParking,
    userState,
    parkingMessages,
    addParkingMessage,
    clearParkingMessages,
  } = useAppStore();

  useEffect(() => {
    // Always start with a clean chat on mount (no history across devices).
    clearParkingMessages();
  }, [clearParkingMessages]);

  useEffect(() => {
    if (userState !== "focusing") {
      setShowThoughtParking(false);
      clearParkingMessages();
    }
  }, [userState, setShowThoughtParking, clearParkingMessages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [parkingMessages, isLoading]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const messageText = input.trim();
    if (!messageText || isLoading) return;

    setInput("");
    addParkingMessage(createMessage("user", messageText));
    setIsLoading(true);

    try {
      const response = await api.parkThought(messageText);
      addParkingMessage(
        createMessage("assistant", response.content || "Thought saved.")
      );
    } catch (error) {
      console.error("Parking error:", error);
      addParkingMessage(
        createMessage(
          "assistant",
          "Sorry, I couldn't save that thought right now."
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {/* Floating trigger button - only show during focus mode */}
      {userState === "focusing" && !showThoughtParking && (
        <button
          onClick={() => setShowThoughtParking(true)}
          className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-accent-foreground shadow-lg transition-transform hover:scale-105 active:scale-95"
          aria-label="Open thought parking"
        >
          <ParkingCircle className="h-6 w-6" />
        </button>
      )}

      <Sheet open={showThoughtParking} onOpenChange={setShowThoughtParking}>
        <SheetContent side="bottom" className="h-[70vh] rounded-t-2xl">
          <SheetHeader className="border-b border-border pb-4">
            <div className="flex items-center justify-between">
              <div>
                <SheetTitle className="flex items-center gap-2">
                  <ParkingCircle className="h-5 w-5 text-accent" />
                  Thought Parking
                </SheetTitle>
                <SheetDescription>
                  A safe place for whatever's on your mind. No judgment here.
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>

          <div className="flex flex-1 flex-col overflow-hidden">
            {/* Messages area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {parkingMessages.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <p className="text-sm text-muted-foreground max-w-xs">
                    Vent, ask random questions, or just dump your thoughts.
                    Everything shared here is safe and won't interrupt your
                    task.
                  </p>
                </div>
              )}

              {parkingMessages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex",
                    message.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-2.5",
                      message.role === "user"
                        ? "bg-accent text-accent-foreground"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {message.content}
                    </p>
                  </div>
                </div>
              ))}

              {isLoading && <PendingIndicator />}

              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-border p-4">
              <form onSubmit={handleSubmit} className="flex gap-2">
                <Textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Whatever's on your mind..."
                  className="min-h-[44px] max-h-24 resize-none text-sm"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmit(e);
                    }
                  }}
                  disabled={isLoading}
                />
                <Button
                  type="submit"
                  size="icon"
                  variant="secondary"
                  disabled={!input.trim() || isLoading}
                  className="h-[44px] w-[44px] shrink-0"
                >
                  <Send className="h-4 w-4" />
                  <span className="sr-only">Send thought</span>
                </Button>
              </form>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
