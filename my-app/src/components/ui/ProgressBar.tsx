
type ProgressBarProps = {
  value: number;
  max?: number;
  label?: string;
};

export default function ProgressBar({ value, max = 100, label }: ProgressBarProps) {
  const percentage = Math.max(0, Math.min(100, (value / max) * 100));

  return (
    <div className="progress-wrap">
      {label && <span className="progress-label">{label}</span>}
      <div className="progress-track" aria-label={label}>
        <div className="progress-fill" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
