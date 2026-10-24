import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, ShieldCheck } from 'lucide-react';
import { useMe, useMySecurityQuestion, useSetSecurityQuestion } from '../../api/hooks';
import { ApiError } from '../../api/client';
import { PasswordField, SelectField, TextField } from '../../components/Field';
import { Button, Spinner } from '../../components/ui';
import { useToast } from '../../components/Toast';
import { SECURITY_ANSWER_MIN_LENGTH, SECURITY_QUESTIONS, normalizeAnswer } from '../../lib/enums';

const schema = z.object({
  question: z.string().refine((v) => SECURITY_QUESTIONS.includes(v), 'Choose a security question.'),
  answer: z
    .string()
    .refine((v) => normalizeAnswer(v).length >= SECURITY_ANSWER_MIN_LENGTH, `Use at least ${SECURITY_ANSWER_MIN_LENGTH} letters or numbers.`),
  current_password: z.string().min(1, 'Enter your current password.'),
});
type Values = z.infer<typeof schema>;

/** Set or change the security question used for self-service password reset. */
export default function SecurityQuestion() {
  const me = useMe();
  const current = useMySecurityQuestion();
  const save = useSetSecurityQuestion();
  const navigate = useNavigate();
  const toast = useToast();
  const home = me.data?.role === 'admin' ? '/admin' : '/';

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<Values>({ resolver: zodResolver(schema), values: current.data ? { question: current.data, answer: '', current_password: '' } : undefined });

  const onSubmit = handleSubmit((values) =>
    save.mutate(values, {
      onSuccess: () => {
        toast('Security question saved');
        navigate(home);
      },
      onError: (err) => {
        if (!(err instanceof ApiError)) return setError('root', { message: 'Something went wrong. Please try again.' });
        for (const [field, message] of Object.entries(err.fields)) setError(field as keyof Values, { message });
        if (!Object.keys(err.fields).length) setError('root', { message: err.message });
      },
    }),
  );

  if (current.isPending) return <Spinner />;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <header className="subpage-header">
        <Link to={home} className="icon-btn" aria-label="Back">
          <ChevronLeft size={22} strokeWidth={2} aria-hidden="true" />
        </Link>
        <h1>Security question</h1>
      </header>
      <form className="form compact" style={{ padding: '8px 20px 24px' }} onSubmit={onSubmit} noValidate>
        <div className="row note" style={{ gap: 10, alignItems: 'flex-start', fontSize: 13 }}>
          <ShieldCheck size={20} strokeWidth={2} aria-hidden="true" style={{ flex: 'none', color: 'var(--success)' }} />
          <span>
            If you ever forget your password, you'll answer this question to set a new one yourself.
            {current.data ? ' Saving replaces your current question and answer.' : ''}
          </span>
        </div>
        {errors.root?.message && (
          <div className="alert danger" role="alert">
            {errors.root.message}
          </div>
        )}
        <SelectField label="Question" options={SECURITY_QUESTIONS} placeholder="Choose a question" error={errors.question?.message} required {...register('question')} />
        <TextField
          label="Answer"
          autoComplete="off"
          spellCheck={false}
          placeholder="Something you'll remember"
          error={errors.answer?.message}
          hint="Capital letters, spaces and punctuation don't matter."
          required
          {...register('answer')}
        />
        <PasswordField
          label="Current password"
          autoComplete="current-password"
          placeholder="To confirm it's you"
          error={errors.current_password?.message}
          required
          {...register('current_password')}
        />
        <Button type="submit" block loading={save.isPending}>
          {save.isPending ? 'Saving…' : 'Save security question'}
        </Button>
      </form>
    </div>
  );
}
