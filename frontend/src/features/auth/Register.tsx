import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft } from 'lucide-react';
import { useLogin, useRegister } from '../../api/hooks';
import { ApiError } from '../../api/client';
import { PasswordField, SelectField, TextField } from '../../components/Field';
import { Button, PasswordStrength } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { MANDAL_NAMES, MANDAL_TYPES } from '../../lib/enums';
import { passwordChecks } from '../../lib/password';

const schema = z
  .object({
    full_name: z.string().trim().min(1, 'Enter your full name.').max(100, 'Keep it under 100 characters.'),
    username: z
      .string()
      .trim()
      .min(3, 'Use at least 3 characters.')
      .max(32, 'Use 32 characters or fewer.')
      .regex(/^[A-Za-z0-9][A-Za-z0-9._-]*$/, 'Use letters, numbers, dots, dashes or underscores.'),
    mandal_name: z.string().refine((v) => MANDAL_NAMES.includes(v), 'Choose your Mandal.'),
    mandal_type: z.string().refine((v) => MANDAL_TYPES.includes(v), 'Choose your Mandal type.'),
    password: z.string().min(1, 'Choose a password.'),
    confirm_password: z.string().min(1, 'Re-enter your password.'),
  })
  .superRefine((v, ctx) => {
    const failed = passwordChecks(v.password).filter((c) => !c.ok);
    if (v.password && failed.length) ctx.addIssue({ code: 'custom', path: ['password'], message: `Password needs: ${failed.map((f) => f.label.toLowerCase()).join(', ')}.` });
    if (v.username.length >= 3 && v.password.toLowerCase().includes(v.username.toLowerCase()))
      ctx.addIssue({ code: 'custom', path: ['password'], message: "Don't include your username in your password." });
    if (v.confirm_password && v.password !== v.confirm_password)
      ctx.addIssue({ code: 'custom', path: ['confirm_password'], message: 'Passwords do not match' });
  });
type Values = z.infer<typeof schema>;

export default function Register() {
  const reg = useRegister();
  const login = useLogin();
  const navigate = useNavigate();
  const toast = useToast();
  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<Values>({
    resolver: zodResolver(schema),
    mode: 'onTouched',
    defaultValues: { mandal_name: '', mandal_type: '' },
  });
  const password = watch('password') ?? '';

  const onSubmit = handleSubmit(async (values) => {
    try {
      await reg.mutateAsync(values);
      await login.mutateAsync({ username: values.username, password: values.password });
      toast('Welcome! Your account is ready.');
      navigate('/', { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        for (const [field, message] of Object.entries(err.fields)) setError(field as keyof Values, { message });
        if (!Object.keys(err.fields).length) setError('root', { message: err.message });
      } else setError('root', { message: 'Something went wrong. Please try again.' });
    }
  });

  return (
    <div className="auth register">
      <header className="subpage-header">
        <Link to="/login" className="icon-btn" aria-label="Back to sign in">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <h1>Create account</h1>
      </header>
      <p className="muted" style={{ padding: '0 24px 16px', fontSize: 14 }}>
        Register once to start logging your seva hours.
      </p>
      <form className="form compact" style={{ padding: '0 24px' }} onSubmit={onSubmit} noValidate>
        {errors.root?.message && (
          <div className="alert danger" role="alert">
            {errors.root.message}
          </div>
        )}
        <TextField label="Full name" autoComplete="name" placeholder="e.g. Anjali Patel" error={errors.full_name?.message} required {...register('full_name')} />
        <TextField
          label="Username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          placeholder="Choose a unique username"
          error={errors.username?.message}
          required
          {...register('username')}
        />
        <div className="grid-2" style={{ gap: 12 }}>
          <SelectField label="Mandal name" options={MANDAL_NAMES} placeholder="Select" error={errors.mandal_name?.message} required {...register('mandal_name')} />
          <SelectField label="Mandal type" options={MANDAL_TYPES} placeholder="Select" error={errors.mandal_type?.message} required {...register('mandal_type')} />
        </div>
        <PasswordField
          label="Password"
          autoComplete="new-password"
          placeholder="At least 12 characters"
          error={errors.password?.message}
          required
          after={<PasswordStrength checks={passwordChecks(password)} />}
          {...register('password')}
        />
        <PasswordField
          label="Confirm password"
          autoComplete="new-password"
          placeholder="Re-enter password"
          error={errors.confirm_password?.message}
          required
          {...register('confirm_password')}
        />
        <Button type="submit" block loading={isSubmitting} style={{ marginTop: 8 }}>
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </Button>
        <p className="muted" style={{ textAlign: 'center', fontSize: 14 }}>
          Already registered?{' '}
          <Link to="/login" style={{ fontWeight: 700 }}>
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
