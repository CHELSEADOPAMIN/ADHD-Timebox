import { Clock, Sun, Moon, BarChart, X } from "lucide-react";

interface HeaderBarProps {
  toggleReview: () => void;
  isReviewOpen: boolean;
  isDark: boolean;
  toggleTheme: () => void;
}

export const HeaderBar = ({
  toggleReview,
  isReviewOpen,
  isDark,
  toggleTheme,
}: HeaderBarProps) => (
  <div className="flex justify-between items-center py-5 shrink-0">
    <div className="flex items-center gap-3">
      <div
        className={`w-10 h-10 rounded-2xl flex items-center justify-center shadow-sm ${
          isDark ? "bg-indigo-500" : "bg-white border border-slate-100"
        }`}
      >
        <Clock
          className={isDark ? "text-white" : "text-indigo-500"}
          size={22}
          strokeWidth={2.5}
        />
      </div>
      <div>
        <h1
          className={`text-2xl font-black tracking-tight leading-none ${
            isDark ? "text-slate-100" : "text-slate-800"
          }`}
        >
          Tymebox
        </h1>
        <p
          className={`text-xs font-bold tracking-wider uppercase ${
            isDark ? "text-slate-500" : "text-slate-400"
          }`}
        >
          Deep Work OS
        </p>
      </div>
    </div>
    <div className="flex gap-3">
      <button
        onClick={toggleTheme}
        className={`p-3 rounded-2xl transition-all ${
          isDark
            ? "text-slate-400 hover:text-white hover:bg-slate-800"
            : "text-slate-400 hover:text-indigo-600 hover:bg-indigo-50"
        }`}
        aria-label="Toggle Theme"
      >
        {isDark ? <Sun size={22} /> : <Moon size={22} />}
      </button>
      <button
        onClick={toggleReview}
        className={`p-3 rounded-2xl transition-all ${
          isDark
            ? "text-slate-400 hover:text-white hover:bg-slate-800"
            : "text-slate-400 hover:text-indigo-600 hover:bg-indigo-50"
        }`}
        aria-label="Toggle Daily Review"
      >
        {isReviewOpen ? <X size={22} /> : <BarChart size={22} />}
      </button>
    </div>
  </div>
);
