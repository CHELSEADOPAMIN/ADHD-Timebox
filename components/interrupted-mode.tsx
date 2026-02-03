"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";
import { getRandomReward } from "@/lib/rewards";
import { CheckCircle, Circle, AlertCircle, ArrowRight, RotateCcw, Coffee } from "lucide-react";

type TaskOutcome = "finished" | "partial" | "stuck" | null;

const COMPLETION_PATTERN = /\b(done|finished|completed|complete|task\s+completed|all\s+done)\b/i;

export function InterruptedMode() {
  const [selectedOutcome, setSelectedOutcome] = useState<TaskOutcome>(null);
  const [showReward, setShowReward] = useState(false);
  const [rewardMessage, setRewardMessage] = useState("");
  const [quickInput, setQuickInput] = useState("");

  const {
    currentTask,
    setCurrentTask,
    setUserState,
    updateTask,
    setTimeRemaining,
    clearPlanningMessages,
    clearParkingMessages,
    setShowThoughtParking,
  } = useAppStore();

  const handleOutcomeSelect = (outcome: TaskOutcome) => {
    setSelectedOutcome(outcome);
    
    // Show appropriate reward
    let rewardType: "survived" | "partialProgress" | "gotStuck" = "survived";
    if (outcome === "partial") rewardType = "partialProgress";
    if (outcome === "stuck") rewardType = "gotStuck";
    
    setRewardMessage(getRandomReward(rewardType));
    setShowReward(true);
  };

  const finalizeOutcome = (outcome: TaskOutcome) => {
    if (currentTask && outcome) {
      const completed = outcome === "finished";
      updateTask(currentTask.id, {
        status: completed ? "completed" : "pooled",
        completedAt: completed ? new Date() : undefined,
        startedAt: completed ? currentTask.startedAt : undefined,
      });
      if (completed) {
        clearPlanningMessages();
      }
      clearParkingMessages();
    }
    setShowThoughtParking(false);
    setCurrentTask(null);
    setTimeRemaining(0);
    setUserState("planning");
    setSelectedOutcome(null);
    setShowReward(false);
    setQuickInput("");
  };

  const handleContinue = () => {
    if (!selectedOutcome) return;
    finalizeOutcome(selectedOutcome);
  };

  const handleTryAgain = () => {
    if (currentTask) {
      const startedAt = new Date();
      updateTask(currentTask.id, { status: "in-progress", startedAt });
      setCurrentTask({ ...currentTask, status: "in-progress", startedAt });
      // Reset timer to original duration
      setTimeRemaining(currentTask.duration * 60);
      setUserState("focusing");
    }
  };

  const handleTakeBreak = () => {
    setUserState("resting");
  };

  const handleQuickSubmit = (event: FormEvent) => {
    event.preventDefault();
    const text = quickInput.trim();
    if (!text) return;
    if (COMPLETION_PATTERN.test(text)) {
      handleOutcomeSelect("finished");
      finalizeOutcome("finished");
      return;
    }
    setQuickInput("");
  };

  if (!currentTask) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="text-center">
          <p className="text-muted-foreground mb-4">No active task</p>
          <Button onClick={() => setUserState("planning")}>
            Start planning
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center">
      <div className="w-full max-w-md">
        {!showReward ? (
          <>
            {/* Task summary */}
            <div className="mb-8 text-center">
              <h2 className="text-xl font-medium text-foreground mb-2">
                Time's up on this tymebox
              </h2>
              <p className="text-muted-foreground">
                How did it go with "{currentTask.title}"?
              </p>
            </div>

            <form onSubmit={handleQuickSubmit} className="mb-6">
              <input
                value={quickInput}
                onChange={(e) => setQuickInput(e.target.value)}
                placeholder='Type "task completed" and press Enter'
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </form>

            {/* Outcome options */}
            <div className="space-y-3 mb-8">
              <button
                onClick={() => handleOutcomeSelect("finished")}
                className={`w-full flex items-center gap-4 rounded-xl border p-4 transition-colors ${
                  selectedOutcome === "finished"
                    ? "border-safe bg-safe/10"
                    : "border-border bg-card hover:bg-secondary"
                }`}
              >
                <CheckCircle className={`h-6 w-6 ${
                  selectedOutcome === "finished" ? "text-safe" : "text-muted-foreground"
                }`} />
                <div className="text-left">
                  <p className="font-medium text-foreground">Finished</p>
                  <p className="text-sm text-muted-foreground">I completed what I set out to do</p>
                </div>
              </button>

              <button
                onClick={() => handleOutcomeSelect("partial")}
                className={`w-full flex items-center gap-4 rounded-xl border p-4 transition-colors ${
                  selectedOutcome === "partial"
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card hover:bg-secondary"
                }`}
              >
                <Circle className={`h-6 w-6 ${
                  selectedOutcome === "partial" ? "text-primary" : "text-muted-foreground"
                }`} />
                <div className="text-left">
                  <p className="font-medium text-foreground">Partial progress</p>
                  <p className="text-sm text-muted-foreground">I made some progress but didn't finish</p>
                </div>
              </button>

              <button
                onClick={() => handleOutcomeSelect("stuck")}
                className={`w-full flex items-center gap-4 rounded-xl border p-4 transition-colors ${
                  selectedOutcome === "stuck"
                    ? "border-accent bg-accent/10"
                    : "border-border bg-card hover:bg-secondary"
                }`}
              >
                <AlertCircle className={`h-6 w-6 ${
                  selectedOutcome === "stuck" ? "text-accent" : "text-muted-foreground"
                }`} />
                <div className="text-left">
                  <p className="font-medium text-foreground">Got stuck</p>
                  <p className="text-sm text-muted-foreground">I hit a wall or couldn't focus</p>
                </div>
              </button>
            </div>
          </>
        ) : (
          <>
            {/* Reward display */}
            <div className="mb-8 text-center">
              <div className="mb-6 inline-flex h-16 w-16 items-center justify-center rounded-full bg-safe/10">
                <CheckCircle className="h-8 w-8 text-safe" />
              </div>
              <p className="text-xl font-medium text-foreground mb-2">
                {rewardMessage}
              </p>
              <p className="text-muted-foreground">
                {selectedOutcome === "finished" && "You completed your tymebox."}
                {selectedOutcome === "partial" && "Progress is progress."}
                {selectedOutcome === "stuck" && "Sometimes that happens. It's okay."}
              </p>
            </div>

            {/* Action buttons */}
            <div className="space-y-3">
              <Button onClick={handleContinue} className="w-full" size="lg">
                <ArrowRight className="mr-2 h-4 w-4" />
                Continue to planning
              </Button>
              
              {selectedOutcome !== "finished" && (
                <Button
                  variant="outline"
                  onClick={handleTryAgain}
                  className="w-full bg-transparent"
                  size="lg"
                >
                  <RotateCcw className="mr-2 h-4 w-4" />
                  Try again with same task
                </Button>
              )}
              
              <Button
                variant="ghost"
                onClick={handleTakeBreak}
                className="w-full text-muted-foreground"
                size="lg"
              >
                <Coffee className="mr-2 h-4 w-4" />
                Take a break first
              </Button>
            </div>
          </>
        )}

        {/* Gentle reminder */}
        <p className="mt-8 text-center text-xs text-muted-foreground/60">
          No matter the outcome, you showed up. That matters.
        </p>
      </div>
    </div>
  );
}
