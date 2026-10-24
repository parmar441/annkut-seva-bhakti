import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { useResetQuestion, useResetWithAnswer } from '../../api/hooks';
import { ApiError, errorMessage } from '../../api/client';
import { PasswordField, TextField } from '../../components/Field';
import { Button, PasswordStrength } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { PASSWORD_MIN_LENGTH } from '../../lib/enums';
import { passwordChecks } from '../../lib/password';

const usernameSchema = z.object({ username: z.string().trim().min(1, 'Enter your username.') });

const resetSchema = z
  .object({
    answer: z.string().trim().min(1, 'Enter your answer.'),
    password: z.string().min(1, 'Choose a new password.'),
    confirm_password: z.string().min(1, 'Re-enter your new password.'),
  })
  .superRefine((v, ctx) => {
    const failed = passwordChecks(v.password).filter((c) => !c.ok);
    if (v.password && failed.length)
      ctx.addIssue({ code: 'custom', path: ['password'], message: `Password needs: ${failed.map((f) => f.label.toLowerCase()).join(', ')}.` });
    if (v.confirm_password && v.password !== v.confirm_password)
      ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: 'Passwords do not match' });
  });
type ResetValues = z.infer<typeof resetSchema>;

function UsernameStep({ onFound }: { onFound: (username: string, question: string) => void }) {
  const lookup = useResetQuestion();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ username: string }>({ resolver: zodResolver(usernameSchema) });
  const onSubmit = handleSubmit(({ username }) =>
    lookup.mutate(username, { onSuccess: (r) => onFound(username, r.question) }),
  );
  return (
    <form className="form compact" style={{ padding: '0 24px' }} onSubmit={onSubmit} noValidate>
      {lookup.isError && (
        <div className="alert danger" role="alert">
          {errorMessage(lookup.error)}
        </div>
      )}
      <TextField
        label="Username"
        large
        autoComplete="username"
        autoCapitalize="none"
        spellCheck={false}
        placeholder="Enter your username"
        error={errors.username?.message}
        {...register('username')}
      />
      <Button type="submit" block loading={lookup.isPending} style={{ marginTop: 8 }}>
        {lookup.isPending ? 'Checking…' : 'Continue'}
      </Button>
    </form>
  );
}

function AnswerStep({ username, question, onBack }: { username: string; question: string; onBack: () => void }) {
  const reset = useResetWithAnswer();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors },
  } = useForm<ResetValues>({ resolver: zodResolver(resetSchema), mode: 'onTouched' });
  const password = watch('password') ?? '';

  const onSubmit = handleSubmit((values) =>
    reset.mutate(
      { username, ...values },
      {
        onSuccess: () => {
          toast('Password changed. Sign in with your new password.');
          navigate('/login', { replace: true });
        },
        onError: (err) => {
          if (!(err instanceof ApiError)) return setError('root', { message: 'Something went wrong. Please try again.' });
          for (const [field, message] of Object.entries(err.fields)) setError(field as keyof ResetValues, { message });
          if (!Object.keys(err.fields).length || err.code === 'WRONG_ANSWER') setError('root', { message: err.message });
        },
      },
    ),
  );

  return (
    <form className="form compact" style={{ padding: '0 24px' }} onSubmit={onSubmit} noValidate>
      {errors.root?.message && (
        <div className="alert danger" role="alert">
          {errors.root.message}
        </div>
      )}
      <div className="card stack-sm" style={{ gap: 2 }}>
        <p className="muted" style={{ fontSize: 12, fontWeight: 600 }}>
          Resetting the password for
        </p>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <strong style={{ fontSize: 15, overflowWrap: 'anywhere' }}>{username}</strong>
          <button type="button" className="btn-link" style={{ padding: '10px 0' }} onClick={onBack}>
            Change
          </button>
        </div>
      </div>
      <TextField
        label={question}
        autoComplete="off"
        spellCheck={false}
        placeholder="Your answer"
        error={errors.answer?.message}
        hint="Capital letters, spaces and punctuation don't matter."
        required
        {...register('answer')}
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
      <Button type="submit" block loading={reset.isPending} style={{ marginTop: 8 }}>
        {reset.isPending ? 'Saving…' : 'Reset password'}
      </Button>
    </form>
  );
}

export default function ForgotPassword() {
  const [found, setFound] = useState<{ username: string; question: string } | null>(null);
  return (
    <div className="auth register">
      <header className="subpage-header">
        <Link to="/login" className="icon-btn" aria-label="Back to sign in">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <h1>Forgot password</h1>
      </header>
      <p className="muted" style={{ padding: '0 24px 16px', fontSize: 14 }}>
        {found ? 'Answer your security question and choose a new password.' : 'Enter your username to see your security question.'}
      </p>
      {found ? (
        <AnswerStep username={found.username} question={found.question} onBack={() => setFound(null)} />
      ) : (
        <UsernameStep onFound={(username, question) => setFound({ username, question })} />
      )}
      <p className="muted" style={{ textAlign: 'center', fontSize: 13, padding: '20px 24px 0' }}>
        Forgot your answer or username? Ask your Mandal organizer for a{' '}
        <Link to="/reset-password" style={{ fontWeight: 700 }}>
          reset code
        </Link>
        .
      </p>
    </div>
  );
}
