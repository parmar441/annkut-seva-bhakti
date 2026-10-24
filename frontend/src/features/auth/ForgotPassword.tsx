import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link } from 'react-router-dom';
import { ChevronLeft, KeyRound } from 'lucide-react';
import { useRequestReset } from '../../api/hooks';
import { errorMessage } from '../../api/client';
import { TextField } from '../../components/Field';
import { Button } from '../../components/ui';

const schema = z.object({ username: z.string().trim().min(1, 'Enter your username.') });
type Values = z.infer<typeof schema>;

export default function ForgotPassword() {
  const request = useRequestReset();
  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit(({ username }) => request.mutate(username));
  const username = getValues('username')?.trim() ?? '';

  return (
    <div className="auth register">
      <header className="subpage-header">
        <Link to="/login" className="icon-btn" aria-label="Back to sign in">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <h1>Forgot password</h1>
      </header>

      {request.isSuccess ? (
        <div className="stack" style={{ padding: '8px 24px', gap: 16 }}>
          <div className="card stack" role="status" style={{ gap: 10 }}>
            <div className="row" style={{ gap: 10 }}>
              <div className="avatar" aria-hidden="true">
                <KeyRound size={20} strokeWidth={2} />
              </div>
              <h2 className="section-title sm">Request sent</h2>
            </div>
            <p className="muted" style={{ fontSize: 14 }}>
              If <strong style={{ color: 'var(--ink)' }}>{username}</strong> is a volunteer account, the organizers can now see your
              request.
            </p>
            <ol className="muted" style={{ fontSize: 14, margin: 0, paddingLeft: 20, display: 'grid', gap: 6 }}>
              <li>Ask your Mandal organizer for your reset code. They will check it's you first.</li>
              <li>Enter the code and choose a new password. The code works once and expires after 30 minutes.</li>
            </ol>
          </div>
          <Link to={`/reset-password?username=${encodeURIComponent(username)}`} className="btn btn-primary btn-block">
            I have a reset code
          </Link>
          <Link to="/login" className="btn btn-secondary btn-block" style={{ height: 52 }}>
            Back to sign in
          </Link>
        </div>
      ) : (
        <>
          <p className="muted" style={{ padding: '0 24px 16px', fontSize: 14 }}>
            Enter your username. An organizer will give you a one-time code to set a new password.
          </p>
          <form className="form compact" style={{ padding: '0 24px' }} onSubmit={onSubmit} noValidate>
            {request.isError && (
              <div className="alert danger" role="alert">
                {errorMessage(request.error)}
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
            <Button type="submit" block loading={request.isPending} style={{ marginTop: 8 }}>
              {request.isPending ? 'Sending…' : 'Request reset code'}
            </Button>
            <Link to="/reset-password" className="btn btn-secondary btn-block" style={{ height: 52 }}>
              I already have a code
            </Link>
          </form>
        </>
      )}
    </div>
  );
}
