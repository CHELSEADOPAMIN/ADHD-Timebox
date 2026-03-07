"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/app/utils/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore } from "@/lib/store";
import { TimerDisplay } from "./timer-display";
import { SessionPlanningPanel } from "./session-planning-panel";
import { getRandomReward } from "@/lib/rewards";
import {
  ArrowRight,
  Coffee,
  HelpCircle,
  Lightbulb,
  Pause,
  ShieldCheck,
  Square,
} from "lucide-react";

const IDLE_THRESHOLD_SECONDS = 120;
const DISTRACTION_THRESHOLD_MS = 30 * 1000;
const FOCUS_POLL_INTERVAL_MS = 15000;
const INTERVENTION_COOLDOWN_MS = 60 * 1000;
// Temporary testing switch:
// default OFF so distraction prompts come from backend SSE/agent logic only.
const ENABLE_FRONTEND_FALLBACK_DETECTION =
  process.env.NEXT_PUBLIC_ENABLE_FRONTEND_DETECTION === "1";
const EVENTS_URL =
  `${process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "http://localhost:8000"}/api/events`;

const GENTLE_NUDGES = [
  "Hey, mind wandered a little?",
  "Quick check-in: still with this task?",
  "No pressure. Want to return to your main thread?",
  "Soft nudge: are we still on this one?",
];

const DISTRACTION_KEYWORDS = [
  { key: "youtube", label: "YouTube", matches: ["youtube"] },
  { key: "netflix", label: "Netflix", matches: ["netflix"] },
  { key: "tiktok", label: "TikTok", matches: ["tiktok"] },
  { key: "instagram", label: "Instagram", matches: ["instagram"] },
  { key: "twitter", label: "X/Twitter", matches: ["twitter", "x.com"] },
  { key: "reddit", label: "Reddit", matches: ["reddit"] },
  { key: "twitch", label: "Twitch", matches: ["twitch"] },
  { key: "bilibili", label: "Bilibili", matches: ["bilibili"] },
  { key: "weibo", label: "Weibo", matches: ["weibo"] },
];

const formatDuration = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0s";
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  if (mins <= 0) return `${secs}s`;
  if (secs === 0) return `${mins}m`;
  return `${mins}m ${secs}s`;
};

const formatMinutesLeft = (seconds: number) => {
  if (!Number.isFinite(seconds) || seconds <= 0) return "0m";
  const mins = Math.max(1, Math.ceil(seconds / 60));
  return `${mins} min`;
};

const parseActiveWindow = (value?: string | null) => {
  const safe = value ?? "";
  if (!safe) return { app: "", title: "" };
  const [app, ...rest] = safe.split(" - ");
  return { app: app?.trim() ?? "", title: rest.join(" - ").trim() };
};

const findDistraction = (value?: string | null) => {
  const haystack = (value ?? "").toLowerCase();
  if (!haystack) return null;
  for (const item of DISTRACTION_KEYWORDS) {
    if (item.matches.some((match) => haystack.includes(match))) {
      return item;
    }
  }
  return null;
};

export function FocusMode() {
  const [showIntervention, setShowIntervention] = useState(false);
  const [interventionReason, setInterventionReason] = useState<
    "idle" | "distraction" | null
  >(null);
  const [interventionMessage, setInterventionMessage] = useState("");
  const [detectedWindow, setDetectedWindow] = useState<string | null>(null);
  const [detectedKey, setDetectedKey] = useState<string | null>(null);
  const [detectedLabel, setDetectedLabel] = useState<string | null>(null);
  const [idleSeconds, setIdleSeconds] = useState<number | null>(null);
  const [sessionWhitelist, setSessionWhitelist] = useState<string[]>([]);
  const [showThoughtInput, setShowThoughtInput] = useState(false);
  const [thoughtInput, setThoughtInput] = useState("");
  const [thoughtSaving, setThoughtSaving] = useState(false);
  const [thoughtError, setThoughtError] = useState<string | null>(null);

  const lastActivityRef = useRef(Date.now());
  const distractionStartRef = useRef<number | null>(null);
  const lastDistractionKeyRef = useRef<string | null>(null);
  const lastInterventionRef = useRef(0);
  const thoughtInputRef = useRef<HTMLTextAreaElement | null>(null);

  const {
    currentTask,
    setCurrentTask,
    setUserState,
    setIsTimerRunning,
    isTimerRunning,
    timeRemaining,
    updateTask,
    setShowThoughtParking,
    clearParkingMessages,
    showThoughtParking,
    userState,
    activeSession,
    archiveActiveSession,
  } = useAppStore();

  const handleActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
  }, []);

  const playGentleTone = useCallback(() => {
    if (typeof window === "undefined") return;
    const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContext) return;

    try {
      const ctx = new AudioContext();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 520;
      gain.gain.value = 0.0001;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const now = ctx.currentTime;
      gain.gain.exponentialRampToValueAtTime(0.05, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.32);
      osc.start(now);
      osc.stop(now + 0.35);
      osc.onended = () => {
        ctx.close();
      };
    } catch (error) {
      console.error("Audio cue failed:", error);
    }
  }, []);

  const triggerIntervention = useCallback(
    (
      reason: "idle" | "distraction",
      options?: {
        windowText?: string | null;
        key?: string | null;
        label?: string | null;
        idleSeconds?: number | null;
        customMessage?: string | null;
      }
    ) => {
      const message =
        options?.customMessage?.trim() ||
        GENTLE_NUDGES[Math.floor(Math.random() * GENTLE_NUDGES.length)];
      setInterventionReason(reason);
      setInterventionMessage(message);
      setDetectedWindow(options?.windowText ?? null);
      setDetectedKey(options?.key ?? null);
      setDetectedLabel(options?.label ?? null);
      setIdleSeconds(options?.idleSeconds ?? null);
      setShowIntervention(true);
      setShowThoughtInput(false);
      setThoughtInput("");
      setThoughtError(null);
      setShowThoughtParking(false);
      lastInterventionRef.current = Date.now();
    },
    [setShowThoughtParking]
  );

  useEffect(() => {
    const events = ["mousemove", "keydown", "click", "scroll", "touchstart"];
    events.forEach((event) => {
      window.addEventListener(event, handleActivity);
    });

    return () => {
      events.forEach((event) => {
        window.removeEventListener(event, handleActivity);
      });
    };
  }, [handleActivity]);

  useEffect(() => {
    if (!showThoughtInput) return;
    thoughtInputRef.current?.focus();
  }, [showThoughtInput]);

  useEffect(() => {
    if (showIntervention) {
      playGentleTone();
    }
  }, [showIntervention, playGentleTone]);

  useEffect(() => {
    if (userState !== "focusing") {
      setShowIntervention(false);
      setShowThoughtInput(false);
      setThoughtInput("");
      setThoughtError(null);
      setSessionWhitelist([]);
      distractionStartRef.current = null;
      lastDistractionKeyRef.current = null;
    }
  }, [userState]);

  useEffect(() => {
    if (!currentTask) {
      setShowIntervention(false);
      setShowThoughtInput(false);
    }
  }, [currentTask]);

  useEffect(() => {
    if (!currentTask) return;
    setSessionWhitelist([]);
    distractionStartRef.current = null;
    lastDistractionKeyRef.current = null;
  }, [currentTask?.id]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    if (userState !== "focusing" || !isTimerRunning || !currentTask) {
      return;
    }

    const source = new EventSource(EVENTS_URL);

    const handleDistraction = (event: MessageEvent<string>) => {
      const now = Date.now();
      if (now - lastInterventionRef.current < INTERVENTION_COOLDOWN_MS) return;

      try {
        const payload = JSON.parse(event.data) as {
          type?: string;
          message?: string;
          window?: string;
        };

        const eventType = (payload?.type || "").toLowerCase();
        const windowText =
          typeof payload?.window === "string" ? payload.window : null;
        const match = findDistraction(windowText);
        const reason = eventType === "idle_alert" ? "idle" : "distraction";
        const customMessage =
          typeof payload?.message === "string" ? payload.message : null;

        triggerIntervention(reason, {
          windowText,
          key: match?.key ?? null,
          label: match?.label ?? null,
          customMessage,
        });
      } catch (error) {
        console.error("Failed to parse distraction event:", error);
      }
    };

    const handleError = () => {
      // Keep polling fallback active; SSE reconnect behavior is browser-managed.
      console.warn("Distraction event stream disconnected; polling fallback remains active.");
    };

    source.addEventListener(
      "distraction",
      handleDistraction as EventListener
    );
    source.addEventListener("error", handleError as EventListener);

    return () => {
      source.removeEventListener(
        "distraction",
        handleDistraction as EventListener
      );
      source.removeEventListener("error", handleError as EventListener);
      source.close();
    };
  }, [userState, isTimerRunning, currentTask?.id, triggerIntervention]);

  useEffect(() => {
    if (!ENABLE_FRONTEND_FALLBACK_DETECTION) {
      return;
    }
    if (!isTimerRunning || showIntervention || showThoughtParking || !currentTask) {
      return;
    }
    let cancelled = false;

    const pollFocusState = async () => {
      if (cancelled) return;
      const now = Date.now();
      if (now - lastInterventionRef.current < INTERVENTION_COOLDOWN_MS) return;

      try {
        const focusState = await api.getFocusState();
        if (cancelled) return;

        const activeWindow = focusState.active_window ?? "";
        const idle =
          typeof focusState.idle_seconds === "number"
            ? focusState.idle_seconds
            : Math.floor((Date.now() - lastActivityRef.current) / 1000);

        if (idle >= IDLE_THRESHOLD_SECONDS) {
          triggerIntervention("idle", {
            idleSeconds: idle,
            windowText: activeWindow,
          });
          return;
        }

        const match = findDistraction(activeWindow);
        const isWhitelisted = match
          ? sessionWhitelist.includes(match.key)
          : false;

        if (match && !isWhitelisted) {
          if (lastDistractionKeyRef.current !== match.key) {
            lastDistractionKeyRef.current = match.key;
            distractionStartRef.current = now;
          }
          if (!distractionStartRef.current) {
            distractionStartRef.current = now;
          }
          if (
            now - distractionStartRef.current >= DISTRACTION_THRESHOLD_MS
          ) {
            triggerIntervention("distraction", {
              windowText: activeWindow,
              key: match.key,
              label: match.label,
              idleSeconds: idle,
            });
          }
          return;
        }

        distractionStartRef.current = null;
        lastDistractionKeyRef.current = null;
      } catch (error) {
        console.error("Failed to poll focus state:", error);
      }
    };

    const interval = setInterval(pollFocusState, FOCUS_POLL_INTERVAL_MS);
    pollFocusState();

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [
    isTimerRunning,
    showIntervention,
    showThoughtParking,
    currentTask,
    sessionWhitelist,
    triggerIntervention,
  ]);

  useEffect(() => {
    if (timeRemaining === 0 && isTimerRunning && currentTask) {
      setIsTimerRunning(false);
      setShowThoughtParking(false);
      clearParkingMessages();
      updateTask(currentTask.id, {
        status: "pooled",
        startedAt: undefined,
        completedAt: undefined,
      });
      setCurrentTask({
        ...currentTask,
        status: "pooled",
        startedAt: undefined,
        completedAt: undefined,
      });
      archiveActiveSession("completed", new Date());
      // Show end-of-tymebox ritual (handled by parent via state)
      setUserState("interrupted");
    }
  }, [
    timeRemaining,
    isTimerRunning,
    currentTask,
    setIsTimerRunning,
    setUserState,
    updateTask,
    setCurrentTask,
    archiveActiveSession,
  ]);

  const handlePause = () => {
    setIsTimerRunning(false);
  };

  const handleResume = () => {
    setIsTimerRunning(true);
  };

  const handleStopTask = () => {
    if (currentTask) {
      setShowThoughtParking(false);
      clearParkingMessages();
      updateTask(currentTask.id, {
        status: "pooled",
        startedAt: undefined,
        completedAt: undefined,
      });
      setCurrentTask({
        ...currentTask,
        status: "pooled",
        startedAt: undefined,
        completedAt: undefined,
      });
    }
    archiveActiveSession("stopped", new Date());
    setIsTimerRunning(false);
    setUserState("interrupted");
  };

  const handleReturnToFocus = () => {
    setShowIntervention(false);
    setShowThoughtInput(false);
    setThoughtError(null);
    lastActivityRef.current = Date.now();
  };

  const handleWhitelist = () => {
    if (!detectedKey) return;
    setSessionWhitelist((prev) =>
      prev.includes(detectedKey) ? prev : [...prev, detectedKey]
    );
    setShowIntervention(false);
    setShowThoughtInput(false);
    distractionStartRef.current = null;
    lastDistractionKeyRef.current = null;
  };

  const handleNeedBreak = () => {
    setShowIntervention(false);
    setIsTimerRunning(false);
    setUserState("resting");
  };

  const handleOpenThoughtInput = () => {
    setShowThoughtInput(true);
    setThoughtError(null);
  };

  const handleSaveThought = async () => {
    const messageText = thoughtInput.trim();
    if (!messageText || thoughtSaving) return;

    setThoughtSaving(true);
    setThoughtError(null);

    try {
      await api.parkThought(messageText, "todo");
      setThoughtInput("");
      setShowThoughtInput(false);
      setShowIntervention(false);
      lastActivityRef.current = Date.now();
    } catch (error) {
      console.error("Parking error:", error);
      setThoughtError("Sorry, I couldn't save that thought right now.");
    } finally {
      setThoughtSaving(false);
    }
  };

  if (!currentTask) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground">No active task</p>
      </div>
    );
  }

  const windowParts = parseActiveWindow(detectedWindow);
  const minutesLeft = formatMinutesLeft(timeRemaining);
  const detailLine =
    interventionReason === "distraction"
      ? `Detected you're in ${windowParts.title || detectedLabel || windowParts.app || "a distracting app"}.`
      : idleSeconds !== null
        ? `You've been idle for ${formatDuration(idleSeconds)}.`
        : "Looks like you've been away for a bit.";

  return (
    <div className="flex flex-1 flex-col items-center justify-center">
      {showIntervention && (
        <div className="gentle-nudge-overlay fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md">
          <div className="gentle-nudge-modal gentle-nudge-glow mx-4 w-full max-w-md rounded-3xl border border-white/10 bg-card/90 p-6 shadow-2xl backdrop-blur-xl">
            <div className="mb-4 flex items-start gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-accent/20">
                <HelpCircle className="h-5 w-5 text-accent" />
              </div>
              <div>
                <p className="text-lg font-semibold text-foreground">
                  {interventionMessage || "Hey, mind wandered a little?"}
                </p>
                <p className="text-sm text-muted-foreground">{detailLine}</p>
                {interventionReason && (
                  <span className="mt-2 inline-flex items-center rounded-full bg-secondary px-2 py-1 text-[10px] uppercase tracking-widest text-muted-foreground">
                    {interventionReason === "distraction"
                      ? "distraction detected"
                      : "idle check-in"}
                  </span>
                )}
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-focus/25 p-4">
              <p className="text-xs uppercase tracking-widest text-muted-foreground">
                Current focus
              </p>
              <p className="mt-1 text-lg font-semibold text-foreground">
                {currentTask.title}
              </p>
              {currentTask.description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {currentTask.description}
                </p>
              )}
              <div className="mt-3 flex items-center justify-between text-sm">
                <span className="text-muted-foreground">Time left</span>
                <span className="font-mono text-foreground">{minutesLeft}</span>
              </div>
            </div>

            <div className="mt-5 flex flex-col gap-2">
              <Button onClick={handleReturnToFocus} className="w-full" size="lg">
                <ArrowRight className="h-4 w-4" />
                Return to focus
              </Button>
              <Button
                variant="outline"
                onClick={handleWhitelist}
                className="w-full bg-transparent"
                size="lg"
                disabled={!detectedKey}
                title={
                  detectedKey
                    ? "Allow this app/site for the rest of the session"
                    : "No app/site detected to whitelist"
                }
              >
                <ShieldCheck className="h-4 w-4" />
                This is work
              </Button>
              <Button
                variant="secondary"
                onClick={handleOpenThoughtInput}
                className="w-full"
                size="lg"
              >
                <Lightbulb className="h-4 w-4" />
                I have a new thought
              </Button>
              <Button
                variant="ghost"
                onClick={handleNeedBreak}
                className="w-full text-muted-foreground"
                size="lg"
              >
                <Coffee className="h-4 w-4" />
                I need a break
              </Button>
            </div>

            {showThoughtInput && (
              <div className="mt-4 rounded-2xl border border-border/60 bg-background/70 p-4">
                <p className="text-sm font-medium text-foreground">
                  Park this thought
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Quick dump, then right back to focus.
                </p>
                <Textarea
                  ref={thoughtInputRef}
                  value={thoughtInput}
                  onChange={(e) => setThoughtInput(e.target.value)}
                  placeholder="Type the thought you want to save..."
                  className="mt-3 min-h-[80px] resize-none text-sm"
                  disabled={thoughtSaving}
                />
                {thoughtError && (
                  <p className="mt-2 text-xs text-destructive">{thoughtError}</p>
                )}
                <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                  <Button
                    onClick={handleSaveThought}
                    className="w-full"
                    disabled={!thoughtInput.trim() || thoughtSaving}
                  >
                    Save thought
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => setShowThoughtInput(false)}
                    className="w-full text-muted-foreground"
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            <p className="mt-4 text-center text-xs text-muted-foreground/70">
              No judgment. Just a gentle nudge back to what matters.
            </p>
          </div>
        </div>
      )}

      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-sm text-muted-foreground italic">
            {getRandomReward("started")}
          </p>
        </div>

        <TimerDisplay />

        <div className="mt-8 flex justify-center gap-3">
          {isTimerRunning ? (
            <Button variant="outline" onClick={handlePause} size="lg">
              <Pause className="mr-2 h-4 w-4" />
              Pause
            </Button>
          ) : (
            <Button onClick={handleResume} size="lg">
              Resume
            </Button>
          )}
          <Button variant="ghost" onClick={handleStopTask} size="lg">
            <Square className="mr-2 h-4 w-4" />
            Stop
          </Button>
        </div>

        <p className="mt-8 text-center text-xs text-muted-foreground/60">
          It's okay to pause. It's okay to stop. You're doing great.
        </p>

        {activeSession && <SessionPlanningPanel session={activeSession} />}
      </div>
    </div>
  );
}
