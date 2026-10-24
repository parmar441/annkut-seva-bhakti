import { forwardRef, useId, useState, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { AlertCircle, Eye, EyeOff } from 'lucide-react';

interface FieldShellProps {
  id: string;
  label: ReactNode;
  error?: string;
  hint?: ReactNode;
  small?: boolean;
  required?: boolean;
  children: ReactNode;
  className?: string;
}

export function FieldShell({ id, label, error, hint, small, required, children, className }: FieldShellProps) {
  return (
    <div className={`field${small ? ' small' : ''}${className ? ` ${className}` : ''}`}>
      <label htmlFor={id}>
        {label}
        {required && (
          <>
            {' '}
            <span className="required" aria-hidden="true">
              *
            </span>
          </>
        )}
      </label>
      {children}
      {error && (
        <p id={`${id}-err`} className="field-error">
          <AlertCircle size={16} aria-hidden="true" />
          {error}
        </p>
      )}
      {hint && !error && (
        <p id={`${id}-hint`} className="field-hint">
          {hint}
        </p>
      )}
    </div>
  );
}

function describedBy(id: string, error?: string, hint?: ReactNode) {
  if (error) return `${id}-err`;
  if (hint) return `${id}-hint`;
  return undefined;
}

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: ReactNode;
  error?: string;
  hint?: ReactNode;
  small?: boolean;
  large?: boolean;
  after?: ReactNode;
};

export const TextField = forwardRef<HTMLInputElement, InputProps>(function TextField(
  { label, error, hint, small, large, id, className, after, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} error={error} hint={hint} small={small} required={required} className={className}>
      <input
        ref={ref}
        id={fid}
        className={`input${large ? ' lg' : ''}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        aria-required={required || undefined}
        {...rest}
      />
      {after}
    </FieldShell>
  );
});

export const PasswordField = forwardRef<HTMLInputElement, InputProps>(function PasswordField(
  { label, error, hint, large, id, after, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  const [show, setShow] = useState(false);
  return (
    <FieldShell id={fid} label={label} error={error} hint={hint} required={required}>
      <div className="password-wrap">
        <input
          ref={ref}
          id={fid}
          type={show ? 'text' : 'password'}
          className={`input${large ? ' lg' : ''}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(fid, error, hint)}
          {...rest}
        />
        <button type="button" className="icon-btn" aria-label={show ? 'Hide password' : 'Show password'} aria-pressed={show} onClick={() => setShow((v) => !v)}>
          {show ? <EyeOff size={22} strokeWidth={1.8} aria-hidden="true" /> : <Eye size={22} strokeWidth={1.8} aria-hidden="true" />}
        </button>
      </div>
      {after}
    </FieldShell>
  );
});

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  label: ReactNode;
  error?: string;
  small?: boolean;
  options: readonly string[];
  placeholder?: string;
};

export const SelectField = forwardRef<HTMLSelectElement, SelectProps>(function SelectField(
  { label, error, small, id, options, placeholder, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} error={error} small={small} required={required}>
      <select ref={ref} id={fid} className="select" aria-invalid={error ? true : undefined} aria-describedby={describedBy(fid, error)} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </FieldShell>
  );
});

type TextAreaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label: ReactNode;
  error?: string;
  hint?: ReactNode;
  small?: boolean;
};

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(function TextArea(
  { label, error, hint, small, id, required, ...rest },
  ref,
) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <FieldShell id={fid} label={label} error={error} hint={hint} small={small} required={required}>
      <textarea
        ref={ref}
        id={fid}
        className="textarea"
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fid, error, hint)}
        aria-required={required || undefined}
        {...rest}
      />
    </FieldShell>
  );
});
