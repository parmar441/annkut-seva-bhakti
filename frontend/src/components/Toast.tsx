import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

type Kind = 'info' | 'error';
export interface ToastAction {
  label: string;
  onClick: () => void;
}
interface ToastItem {
  id: number;
  text: string;
  kind: Kind;
  action?: ToastAction;
}

const ToastContext = createContext<(text: string, kind?: Kind, action?: ToastAction) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const show = useCallback((text: string, kind: Kind = 'info', action?: ToastAction) => {
    const id = next.current++;
    setItems((cur) => [...cur.slice(-2), { id, text, kind, action }]);
    // Toasts with an action (e.g. Undo) stay longer so there's time to use it.
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), action ? 10000 : kind === 'error' ? 6000 : 3500);
  }, []);
  const dismiss = (id: number) => setItems((cur) => cur.filter((t) => t.id !== id));

  const value = useMemo(() => show, [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast${t.kind === 'error' ? ' error' : ''}`}>
            <span>{t.text}</span>
            {t.action && (
              <button
                type="button"
                className="toast-action"
                onClick={() => {
                  dismiss(t.id);
                  t.action!.onClick();
                }}
              >
                {t.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
