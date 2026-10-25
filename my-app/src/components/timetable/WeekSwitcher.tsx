
type WeekSwitcherProps = {
  days: string[];
  selected: number;
  onChange: (index: number) => void;
};

export default function WeekSwitcher({ days, selected, onChange }: WeekSwitcherProps) {
  return (
    <div className="week-switcher" role="tablist" aria-label="Timetable days">
      {days.map((day, index) => (
        <button
          key={day}
          type="button"
          className={selected === index ? 'selected' : ''}
          onClick={() => onChange(index)}
          role="tab"
          aria-selected={selected === index}
        >
          {day}
        </button>
      ))}
    </div>
  );
}
