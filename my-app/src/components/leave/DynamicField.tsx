import React from 'react';

export type LeaveField = {
  name: string;
  label: string;
  type: 'text' | 'date' | 'time' | 'textarea' | 'select' | 'tel';
  required?: boolean;
  placeholder?: string;
  options?: string[];
};

type Props = {
  field: LeaveField;
  value: string;
  onChange: (value: string) => void;
};

export default function DynamicField({ field, value, onChange }: Props) {
  const common = {
    id: field.name,
    name: field.name,
    value,
    required: field.required,
    placeholder: field.placeholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => onChange(e.target.value),
  };

  if (field.type === 'textarea') {
    return (
      <label className="dynamic-field">
        <span>{field.label}{field.required ? ' *' : ''}</span>
        <textarea {...common} rows={4} />
      </label>
    );
  }

  if (field.type === 'select') {
    return (
      <label className="dynamic-field">
        <span>{field.label}{field.required ? ' *' : ''}</span>
        <select {...common}>
          <option value="">Select {field.label.toLowerCase()}</option>
          {(field.options ?? []).map(option => <option key={option} value={option}>{option}</option>)}
        </select>
      </label>
    );
  }

  return (
    <label className="dynamic-field">
      <span>{field.label}{field.required ? ' *' : ''}</span>
      <input {...common} type={field.type} />
    </label>
  );
}
