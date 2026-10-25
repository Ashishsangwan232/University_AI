
type Props = {
  onNew: () => void;
};

export default function LeaveSuccess({ onNew }: Props) {
  return (
    <div className="leave-success panel">
      <div className="success-icon">✓</div>
      <span className="eyebrow">Application submitted</span>
      <h2>Your leave request is ready</h2>
      <p>The prototype has completed the review flow. In the connected version, the approved portal tool will submit the application and return its status.</p>
      <button className="primary-btn" type="button" onClick={onNew}>Create another request</button>
    </div>
  );
}
