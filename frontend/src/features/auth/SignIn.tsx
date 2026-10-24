import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useLogin } from '../../api/hooks';
import { ApiError } from '../../api/client';
import { PasswordField, TextField } from '../../components/Field';
import { Button, Logo } from '../../components/ui';

const schema = z.object({
  username: z.string().trim().min(1, 'Enter your username.'),
  password: z.string().min(1, 'Enter your password.'),
});
type Values = z.infer<typeof schema>;

export default function SignIn() {
  const login = useLogin();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema) });

  const onSubmit = handleSubmit((values) =>
    login.mutate(values, {
      onSuccess: ({ user }) => navigate(from && from !== '/login' ? from : user.role === 'admin' ? '/admin' : '/', { replace: true }),
    }),
  );

  const serverError = login.error instanceof ApiError ? login.error.message : login.error ? 'Something went wrong. Please try again.' : null;

  return (
    <div className="auth">
      <div className="brand">
        <Logo />
        <h1>Annkut Seva Bhakti</h1>
        <p>Track your seva hours with ease</p>
      </div>
      <form className="form" style={{ marginTop: 40 }} onSubmit={onSubmit} noValidate>
        {serverError && (
          <div className="alert danger" role="alert">
            {serverError}
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
        <PasswordField
          label="Password"
          large
          autoComplete="current-password"
          placeholder="Enter your password"
          error={errors.password?.message}
          {...register('password')}
        />
        <Button type="submit" block loading={login.isPending} style={{ marginTop: 8 }}>
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
      <div className="spacer" style={{ minHeight: 32 }} />
      <div className="stack" style={{ alignItems: 'center', gap: 10 }}>
        <p className="muted" style={{ fontSize: 15 }}>
          First time doing seva with us?
        </p>
        <Link to="/register" className="btn btn-secondary btn-block" style={{ height: 52 }}>
          Create volunteer account
        </Link>
        <p className="muted" style={{ fontSize: 12, marginTop: 8, textAlign: 'center' }}>
          Admin accounts are set up by organizers only.
        </p>
      </div>
    </div>
  );
}
