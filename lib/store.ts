import { create } from "zustand";
import { persist } from "zustand/middleware";

// User states as defined in the spec
export type UserState = "planning" | "focusing" | "interrupted" | "resting";

export interface Task {
  id: string;
  title: string;
  description?: string;
  duration: number; // in minutes
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  status: "pending" | "pooled" | "in-progress" | "completed" | "partial" | "stuck";
}

export interface ThoughtEntry {
  id: string;
  content: string;
  type: "vent" | "question" | "thought" | "resistance";
  createdAt: Date;
  taskId?: string;
  answered?: boolean;
  answer?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  channel: "planning" | "parking";
}

interface AppState {
  // Hydration
  hasHydrated: boolean;
  setHasHydrated: (value: boolean) => void;

  // Onboarding
  hasCompletedOnboarding: boolean;
  setHasCompletedOnboarding: (value: boolean) => void;

  // User state
  userState: UserState;
  setUserState: (state: UserState) => void;

  // Current task
  currentTask: Task | null;
  setCurrentTask: (task: Task | null) => void;

  // Tasks history
  tasks: Task[];
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;

  // Thought parking
  thoughts: ThoughtEntry[];
  addThought: (thought: ThoughtEntry) => void;
  updateThought: (id: string, updates: Partial<ThoughtEntry>) => void;

  // Chat messages
  planningMessages: ChatMessage[];
  parkingMessages: ChatMessage[];
  addPlanningMessage: (message: ChatMessage) => void;
  addParkingMessage: (message: ChatMessage) => void;
  clearPlanningMessages: () => void;
  clearParkingMessages: () => void;

  // Timer
  timeRemaining: number; // in seconds
  setTimeRemaining: (time: number) => void;
  isTimerRunning: boolean;
  setIsTimerRunning: (running: boolean) => void;

  // UI state
  showThoughtParking: boolean;
  setShowThoughtParking: (show: boolean) => void;

  // Reset for new session
  resetSession: () => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Hydration
      hasHydrated: false,
      setHasHydrated: (hasHydrated) => set({ hasHydrated }),

      // Onboarding
      hasCompletedOnboarding: false,
      setHasCompletedOnboarding: (value) =>
        set({ hasCompletedOnboarding: value }),

      // User state
      userState: "planning",
      setUserState: (userState) => set({ userState }),

      // Current task
      currentTask: null,
      setCurrentTask: (currentTask) => set({ currentTask }),

      // Tasks
      tasks: [],
      setTasks: (tasks) => set({ tasks }),
      addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),
      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
        })),

      // Thoughts
      thoughts: [],
      addThought: (thought) =>
        set((state) => ({ thoughts: [...state.thoughts, thought] })),
      updateThought: (id, updates) =>
        set((state) => ({
          thoughts: state.thoughts.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        })),

      // Chat
      planningMessages: [],
      parkingMessages: [],
      addPlanningMessage: (message) =>
        set((state) => ({
          planningMessages: [...state.planningMessages, message],
        })),
      addParkingMessage: (message) =>
        set((state) => ({
          parkingMessages: [...state.parkingMessages, message],
        })),
      clearPlanningMessages: () => set({ planningMessages: [] }),
      clearParkingMessages: () => set({ parkingMessages: [] }),

      // Timer
      timeRemaining: 0,
      setTimeRemaining: (timeRemaining) => set({ timeRemaining }),
      isTimerRunning: false,
      setIsTimerRunning: (isTimerRunning) => set({ isTimerRunning }),

      // UI
      showThoughtParking: false,
      setShowThoughtParking: (showThoughtParking) => set({ showThoughtParking }),

      // Reset
      resetSession: () =>
        set({
          currentTask: null,
          timeRemaining: 0,
          isTimerRunning: false,
          userState: "planning",
        }),
    }),
    {
      name: "adhd-tymebox-storage",
      version: 2,
      migrate: (persisted) => {
        const state = (persisted ?? {}) as Partial<AppState>;
        return {
          ...state,
          // Always drop chat history on load.
          planningMessages: [],
          parkingMessages: [],
        } as Partial<AppState>;
      },
      partialize: (state) => ({
        hasCompletedOnboarding: state.hasCompletedOnboarding,
        // Persist only unfinished tasks so they survive reloads until completed.
        tasks: state.tasks.filter((task) => {
          const status = task.status?.toLowerCase?.() ?? "";
          return status !== "completed" && status !== "done" && status !== "complete";
        }),
        thoughts: state.thoughts,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    }
  )
);
