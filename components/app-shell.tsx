"use client";

import { useEffect } from "react";
import { api } from "@/app/utils/api";
import { toStoreTask } from "@/app/utils/taskAdapter";
import { useAppStore } from "@/lib/store";
import { StateIndicator } from "./state-indicator";
import { PlanningMode } from "./planning-mode";
import { FocusMode } from "./focus-mode";
import { InterruptedMode } from "./interrupted-mode";
import { RestingMode } from "./resting-mode";
import { ThoughtParkingSheet } from "./thought-parking-sheet";
import { OnboardingDialog } from "./onboarding-dialog";
import { Sidebar } from "./sidebar";
import { LogoLockup } from "./logo-lockup";
import { CalendarModal } from "./calendar-modal";
import { HistoryMode } from "./history-mode";

export function AppShell() {
  const {
    userState,
    hasCompletedOnboarding,
    hasHydrated,
    setHasHydrated,
    setTasks,
    appView,
    archivedSessions,
  } = useAppStore();

  useEffect(() => {
    if (hasHydrated) return;
    const timer = setTimeout(() => {
      setHasHydrated(true);
    }, 500);
    return () => clearTimeout(timer);
  }, [hasHydrated, setHasHydrated]);

  useEffect(() => {
    if (!hasHydrated) return;

    let isMounted = true;

    const loadTasks = async () => {
      try {
        const backendTasks = await api.getTasks();
        if (!isMounted) return;
        setTasks(backendTasks.map(toStoreTask));
      } catch (error) {
        console.error("Failed to load tasks from backend", error);
      }
    };

    loadTasks();

    return () => {
      isMounted = false;
    };
  }, [hasHydrated, setTasks]);

  if (!hasHydrated) {
    return <div className="min-h-screen bg-background" aria-hidden="true" />;
  }

  const renderCurrentMode = () => {
    if (appView === "history") {
      return <HistoryMode sessions={archivedSessions} />;
    }

    console.log("AppShell rendering mode. userState:", userState);
    switch (userState) {
      case "planning":
        return <PlanningMode />;
      case "focusing":
        return <FocusMode />;
      case "interrupted":
        return <InterruptedMode />;
      case "resting":
        return <RestingMode />;
      default:
        return <PlanningMode />;
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-sm">
        <div className="flex h-14 items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-3">
            <LogoLockup />
          </div>
          <div className="flex items-center gap-3">
            <StateIndicator />
          </div>
        </div>
      </header>

      {/* Sidebar - fixed position, hidden on mobile */}
      <Sidebar />

      {/* Main content - with left margin to account for fixed sidebar */}
      <main className="flex flex-1 flex-col lg:ml-16">
        <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-4 py-6">
          {renderCurrentMode()}
        </div>
      </main>

      {/* Thought parking sheet */}
      <ThoughtParkingSheet />

      {/* Onboarding */}
      {!hasCompletedOnboarding && <OnboardingDialog />}

      {/* Calendar modal */}
      <CalendarModal />
    </div>
  );
}
