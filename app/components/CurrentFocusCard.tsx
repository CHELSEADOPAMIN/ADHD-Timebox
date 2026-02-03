import { Play } from "lucide-react";
import { FocusState, FOCUS_STATES } from "../types";
import { MICROCOPY } from "../constants";
import { TymeboxSelector } from "./TymeboxSelector";
import { CompletionCard } from "./CompletionCard";

interface CurrentFocusCardProps {
  focusState: FocusState;
  activeTaskTitle?: string;
  remainingSeconds: number;
  selectedDuration: number;
  actions: {
    start: (taskId: string | null, duration: number) => void;
    pause: () => void;
    resume: () => void;
    abandon: () => void;
    reset: () => void;
    setDuration: (mins: number) => void;
  };
  canStart: boolean;
  isDark: boolean;
}

export const CurrentFocusCard = ({
  focusState,
  activeTaskTitle,
  remainingSeconds,
  selectedDuration,
  actions,
  canStart,
  isDark,
}: CurrentFocusCardProps) => {
  const isPaused = focusState === FOCUS_STATES.PAUSED;
  const isCompleted = focusState === FOCUS_STATES.COMPLETED;
  const isIdle = focusState === FOCUS_STATES.IDLE;

  const cardBg = isDark
    ? "bg-slate-900 border-slate-800"
    : "bg-white border-slate-100";
  const textColor = isDark ? "text-white" : "text-slate-800";

  return (
    <div
      className={`${cardBg} rounded-[2.5rem] p-8 md:p-12 mb-6 md:mb-0 relative overflow-hidden border shadow-xl transition-colors duration-300 h-full flex flex-col min-h-[500px]`}
    >
      {/* State: PAUSED (Fallback View - Full screen handles this now but keeping robust) */}
      {isPaused && (
        <div className="opacity-40 grayscale pointer-events-none blur-sm select-none flex flex-col h-full justify-center">
          <h2 className={`text-3xl font-black text-center mb-4 ${textColor}`}>
            {activeTaskTitle || "Deep Work"}
          </h2>
          <div
            className={`text-center font-mono text-6xl font-bold ${textColor}`}
          >
            Paused
          </div>
          <div className="text-center mt-4 font-bold uppercase tracking-widest text-slate-400">
            Session Paused
          </div>
        </div>
      )}

      {/* State: COMPLETED */}
      {isCompleted && (
        <CompletionCard onReset={actions.reset} isDark={isDark} />
      )}

      {/* State: IDLE */}
      {isIdle && (
        <div className="animate-fade-in flex flex-col h-full justify-center">
          <div className="flex-1 flex flex-col justify-center">
            <h2
              className={`text-3xl md:text-4xl font-black mb-12 text-center leading-tight ${textColor}`}
            >
              {activeTaskTitle ? (
                <>
                  Focus on{" "}
                  <span
                    className={isDark ? "text-indigo-400" : "text-indigo-500"}
                  >
                    {activeTaskTitle}
                  </span>
                </>
              ) : (
                "Ready to focus?"
              )}
            </h2>

            <TymeboxSelector
              selected={selectedDuration}
              onSelect={actions.setDuration}
              disabled={false}
              isDark={isDark}
            />
          </div>

          <div className="shrink-0">
            <button
              onClick={() => actions.start(null, selectedDuration)}
              disabled={!canStart}
              className={`
                 w-full py-6 md:py-8 rounded-3xl font-bold text-2xl transition-all flex justify-center items-center gap-3 relative overflow-hidden group shadow-lg
                 ${
                   canStart
                     ? isDark
                       ? "bg-indigo-600 text-white hover:bg-indigo-500 hover:shadow-indigo-500/20 hover:scale-[1.01]"
                       : "bg-indigo-500 text-white hover:bg-indigo-600 hover:shadow-indigo-200 hover:scale-[1.01]"
                     : isDark
                     ? "bg-slate-800 text-slate-600 cursor-not-allowed"
                     : "bg-slate-100 text-slate-300 cursor-not-allowed"
                 }
               `}
            >
              <Play
                size={28}
                fill="currentColor"
                className={
                  canStart
                    ? "group-hover:translate-x-1 transition-transform"
                    : ""
                }
              />
              {MICROCOPY.idle.cta}
            </button>

            {!canStart && (
              <p
                className={`text-center text-xs mt-6 font-bold tracking-wide opacity-50 ${
                  isDark ? "text-slate-500" : "text-slate-400"
                }`}
              >
                SELECT A TASK & TIME TO BEGIN
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
