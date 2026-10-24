import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { useConfirmReset } from '../../api/hooks';
import { ApiError } from '../../api/client';
import { PasswordField, TextField } from '../../components/Field';
import { Button, PasswordStrength } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { PASSWORD_MIN_LENGTH } from '../../lib/enums';
import { passwordChecks } from '../../lib/password';

const schema = z
  .object({
    username: z.string().trim().min(1, 'Enter your username.'),
    code: z
      .string()
      .transform((v) => v.toUpperCase().replace(/[^A-Z0-9]/g, ''))
      .refine((v) => v.length === 8, 'The code has 8 letters and numbers, like K7Q2-M9XD.'),
    password: z.string().min(1, 'Choose a new password.'),
    confirm_password: z.string().min(1, 'Re-enter your new password.'),
  })
  .superRefine((v, ctx) => {
    const failed = passwordChecks(v.password).filter((c) => !c.ok);
    if (v.password && failed.length)
      ctx.addIssue({ code: 'custom', path: ['password'], message: `Password needs: ${failed.map((f) => f.label.toLowerCase()).join(', ')}.` });
    if (v.username.length >= 3 && v.password.toLowerCase().includes(v.username.toLowerCase()))
      ctx.addIssue({ code: 'custom', path: ['password'], message: "Don't include your username in your password." });
    if (v.confirm_password && v.password !== v.confirm_password)
      ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: 'Passwords do not match' });
  });
type Input = z.input<typeof schema>;
type Values = z.output<typeof schema>;

export default function ResetPassword() {
  const [params] = useSearchParams();
  const confirm = useConfirmReset();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<Input, unknown, Values>({
    resolver: zodResolver(schema),
    mode: 'onTouched',
    defaultValues: { username: params.get('username') ?? '', code: '' },
  });
  const password = watch('password') ?? '';

  const onSubmit = handleSubmit((values) =>
    confirm.mutate(values, {
      onSuccess: () => {
        toast('Password changed. Sign in with your new password.');
        navigate('/login', { replace: true });
      },
      onError: (err) => {
        if (!(err instanceof ApiError)) return setError('root', { message: 'Something went wrong. Please try again.' });
        for (const [field, message] of Object.entries(err.fields)) setError(field as keyof Input, { message });
        setError('root', { message: err.message });
      },
    }),
  );

  return (
    <div className="auth register">
      <header className="subpage-header">
        <Link to="/forgot-password" className="icon-btn" aria-label="Back">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <h1>Set a new password</h1>
      </header>
      <p className="muted" style={{ padding: '0 24px 16px', fontSize: 14 }}>
        Enter the one-time code your Mandal organizer gave you.
      </p>
      <form className="form compact" style={{ padding: '0 24px' }} onSubmit={onSubmit} noValidate>
        {errors.root?.message && (
          <div className="alert danger" role="alert">
            {errors.root.message}
          </div>
        )}
        <TextField
          label="Username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="Your username"
          error={errors.username?.message}
          required
          {...register('username')}
        />
        <TextField
          label="Reset code"
          autoComplete="one-time-code"
          autoCapitalize="characters"
          spellCheck={false}
          placeholder="e.g. K7Q2-M9XD"
          maxLength={12}
          style={{ letterSpacing: '0.12em', fontWeight: 700, textTransform: 'uppercase' }}
          error={errors.code?.message}
          hint="Ask your organizer for this code. It works once and expires after 30 minutes."
          required
          {...register('code')}
        />
        <PasswordField
          label="New password"
          autoComplete="new-password"
          placeholder={`At least ${PASSWORD_MIN_LENGTH} characters`}
          error={errors.password?.message}
          required
          after={<PasswordStrength checks={passwordChecks(password)} />}
          {...register('password')}
        />
        <PasswordField
          label="Confirm new password"
          autoComplete="new-password"
          placeholder="Re-enter password"
          error={errors.confirm_password?.message}
          required
          {...register('confirm_password')}
        />
        <Button type="submit" block loading={confirm.isPending} style={{ marginTop: 8 }}>
          {confirm.isPending ? 'Saving…' : 'Set new password'}
        </Button>
        <p className="muted" style={{ textAlign: 'center', fontSize: 14 }}>
          Know your security answer? <Link to="/forgot-password" style={{ fontWeight: 700 }}>Reset it yourself</Link>
        </p>
      </form>
    </div>
  );
}
