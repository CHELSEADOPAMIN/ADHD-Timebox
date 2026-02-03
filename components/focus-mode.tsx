"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";
import { TimerDisplay } from "./timer-display";
import { getRandomReward } from "@/lib/rewards";
import { Pause, Square, Hand, Coffee } from "lucide-react";

const INACTIVITY_THRESHOLD = 5 * 60 * 1000; // 5 minutes in milliseconds

export function FocusMode() {
  const [showCheckin, setShowCheckin] = useState(false);
  const [checkinMessage, setCheckinMessage] = useState("");
  const lastActivityRef = useRef(Date.now());
  const checkinTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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
  } = useAppStore();

  // Gentle check-in messages
  const checkinMessages = [
    "Hey, just checking in — are you still with this task?",
    "Still here? No pressure, just checking.",
    "How's it going? Need anything?",
    "Taking a moment to check in with you.",
  ];

  // Track user activity
  const handleActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
    if (showCheckin) {
      setShowCheckin(false);
    }
  }, [showCheckin]);

  // Set up activity listeners
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

  // Check for inactivity
  useEffect(() => {
    if (!isTimerRunning) return;

    const checkInactivity = () => {
      const timeSinceLastActivity = Date.now() - lastActivityRef.current;
      
      if (timeSinceLastActivity >= INACTIVITY_THRESHOLD && !showCheckin) {
        setCheckinMessage(
          checkinMessages[Math.floor(Math.random() * checkinMessages.length)]
        );
        setShowCheckin(true);
      }
    };

    const interval = setInterval(checkInactivity, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, [isTimerRunning, showCheckin, checkinMessages]);

  // Handle timer end
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
    setShowThoughtParking,
    clearParkingMessages,
  ]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (checkinTimeoutRef.current) {
        clearTimeout(checkinTimeoutRef.current);
      }
    };
  }, []);

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
    setIsTimerRunning(false);
    setUserState("interrupted");
  };

  const handleImDistracted = () => {
    setShowCheckin(false);
    setShowThoughtParking(true);
  };

  const handleStillHere = () => {
    setShowCheckin(false);
    lastActivityRef.current = Date.now();
  };

  const handleNeedBreak = () => {
    setShowCheckin(false);
    setShowThoughtParking(false);
    setIsTimerRunning(false);
    setUserState("resting");
  };

  if (!currentTask) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <p className="text-muted-foreground">No active task</p>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center">
      {/* Gentle check-in overlay */}
      {showCheckin && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="mx-4 w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-lg">
            <p className="mb-6 text-center text-lg text-foreground">
              {checkinMessage}
            </p>
            <div className="flex flex-col gap-2">
              <Button onClick={handleStillHere} className="w-full">
                I'm still here
              </Button>
              <Button
                variant="outline"
                onClick={handleImDistracted}
                className="w-full bg-transparent"
              >
                <Hand className="mr-2 h-4 w-4" />
                I'm distracted
              </Button>
              <Button
                variant="ghost"
                onClick={handleNeedBreak}
                className="w-full text-muted-foreground"
              >
                <Coffee className="mr-2 h-4 w-4" />
                I need a break
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Focus content */}
      <div className="w-full max-w-sm">
        {/* Reward message on start */}
        <div className="mb-8 text-center">
          <p className="text-sm text-muted-foreground italic">
            {getRandomReward("started")}
          </p>
        </div>

        {/* Timer */}
        <TimerDisplay />

        {/* Controls */}
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

        {/* Gentle reminder */}
        <p className="mt-8 text-center text-xs text-muted-foreground/60">
          It's okay to pause. It's okay to stop. You're doing great.
        </p>
      </div>
    </div>
  );
}
