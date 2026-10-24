import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';

type Kind = 'info' | 'error';
interface ToastItem {
  id: number;
  text: string;
  kind: Kind;
}

const ToastContext = createContext<(text: string, kind?: Kind) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);

  const show = useCallback((text: string, kind: Kind = 'info') => {
    const id = next.current++;
    setItems((cur) => [...cur.slice(-2), { id, text, kind }]);
    setTimeout(() => setItems((cur) => cur.filter((t) => t.id !== id)), kind === 'error' ? 6000 : 3500);
  }, []);

  const value = useMemo(() => show, [show]);
  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast${t.kind === 'error' ? ' error' : ''}`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
