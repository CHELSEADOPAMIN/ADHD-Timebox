"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useAppStore } from "@/lib/store";

const steps = [
  {
    title: "Welcome",
    content:
      "This is a safe space for getting things done. No pressure. No judgment.",
  },
  {
    title: "How it works",
    content:
      "You'll work in short tymeboxes. One task at a time. The goal is to try, not to be perfect.",
  },
  {
    title: "Interruptions happen",
    content:
      "When you get distracted, that's okay. We'll help you notice gently and decide what to do next.",
  },
  {
    title: "Stopping is valid",
    content:
      "You can stop anytime. Stopping safely is a skill. There's no failure here.",
  },
  {
    title: "Ready?",
    content:
      "Let's start by figuring out what you want to work on. Take your time.",
  },
];

export function OnboardingDialog() {
  const [currentStep, setCurrentStep] = useState(0);
  const { setHasCompletedOnboarding, hasCompletedOnboarding } = useAppStore();

  if (hasCompletedOnboarding) return null;

  const isLastStep = currentStep === steps.length - 1;
  const step = steps[currentStep];

  const handleNext = () => {
    if (isLastStep) {
      setHasCompletedOnboarding(true);
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handleSkip = () => {
    setHasCompletedOnboarding(true);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/95 backdrop-blur-sm">
      <div className="mx-4 flex w-full max-w-md flex-col items-center text-center">
        {/* Progress dots */}
        <div className="mb-8 flex gap-2">
          {steps.map((_, index) => (
            <div
              key={index}
              className={`h-1.5 w-8 rounded-full transition-colors duration-300 ${
                index <= currentStep ? "bg-primary" : "bg-muted"
              }`}
            />
          ))}
        </div>

        {/* Content */}
        <div className="mb-12 space-y-4">
          <h1 className="text-2xl font-medium tracking-tight text-foreground">
            {step.title}
          </h1>
          <p className="text-lg leading-relaxed text-muted-foreground">
            {step.content}
          </p>
        </div>

        {/* Actions */}
        <div className="flex w-full flex-col gap-3">
          <Button
            onClick={handleNext}
            className="w-full py-6 text-base"
            size="lg"
          >
            {isLastStep ? "Let's begin" : "Continue"}
          </Button>
          {!isLastStep && (
            <button
              onClick={handleSkip}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              Skip intro
            </button>
          )}
        </div>

        {/* Gentle reminder */}
        <p className="mt-8 text-xs text-muted-foreground/60">
          You can always take breaks. This is here to help, not pressure.
        </p>
      </div>
    </div>
  );
}
