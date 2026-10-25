import type { LeaveField } from './DynamicField';

type Props = {
  fields: LeaveField[];
  values: Record<string, string>;
  onBack: () => void;
  onConfirm: () => void;
};

export default function LeaveReview({ fields, values, onBack, onConfirm }: Props) {
  return (
    <div className="leave-review panel">
      <div className="review-heading">
        <div>
          <span className="eyebrow">Step 2 of 2</span>
          <h2>Review application</h2>
        </div>
        <span className="review-ready">Ready to submit</span>
      </div>

      <div className="review-list">
        {fields.map(field => (
          <div className="review-row" key={field.name}>
            <span>{field.label}</span>
            <strong>{values[field.name] || '—'}</strong>
          </div>
        ))}
      </div>

      <div className="review-note">
        Please check these details before submitting. In the final version, this action will submit through the approved college/hostel portal.
      </div>

      <div className="form-actions">
        <button className="secondary-btn" type="button" onClick={onBack}>Back to form</button>
        <button className="primary-btn" type="button" onClick={onConfirm}>Confirm & submit</button>
      </div>
    </div>
  );
}
