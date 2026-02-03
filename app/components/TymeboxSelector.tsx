interface TymeboxSelectorProps {
  selected: number;
  onSelect: (minutes: number) => void;
  disabled: boolean;
  isDark: boolean;
}

export const TymeboxSelector = ({
  selected,
  onSelect,
  disabled,
  isDark,
}: TymeboxSelectorProps) => {
  const options = [15, 30, 45, 60];
  return (
    <div
      className={`grid grid-cols-4 gap-3 mb-8 ${
        disabled ? "opacity-30 pointer-events-none" : ""
      }`}
    >
      {options.map((min) => (
        <button
          key={min}
          onClick={() => onSelect(min)}
          className={`
            py-5 rounded-2xl text-sm font-bold transition-all relative overflow-hidden group
            ${
              selected === min
                ? isDark
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-900/50 ring-2 ring-indigo-400/20 scale-105"
                  : "bg-indigo-500 text-white shadow-lg shadow-indigo-200 ring-2 ring-indigo-100 scale-105"
                : isDark
                ? "bg-slate-800/40 text-slate-400 hover:bg-slate-800 hover:text-slate-200 border border-transparent"
                : "bg-white text-slate-400 hover:bg-slate-50 hover:text-indigo-600 border border-slate-100 hover:border-indigo-100"
            }
          `}
        >
          <span className="relative z-10 text-lg">
            {min}
            <span className="text-xs font-bold opacity-60 ml-0.5">m</span>
          </span>
        </button>
      ))}
    </div>
  );
};
