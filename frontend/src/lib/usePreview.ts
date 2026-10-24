import { useEffect, useState } from 'react';
import type { Preview } from '../api/types';

/** Debounced server preview of a time range. The duration shown always comes from the server. */
export function usePreview(
  fetcher: (body: { clock_in: string; clock_out?: string }) => Promise<Preview>,
  clockIn: string | null,
  clockOut: string | null,
  deps: unknown[] = [],
) {
  const [state, setState] = useState<{ data: Preview | null; loading: boolean; error: string | null }>({ data: null, loading: false, error: null });

  useEffect(() => {
    if (!clockIn) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    const t = setTimeout(() => {
      fetcher({ clock_in: clockIn, clock_out: clockOut ?? undefined })
        .then((data) => !cancelled && setState({ data, loading: false, error: null }))
        .catch((e: Error) => !cancelled && setState({ data: null, loading: false, error: e.message }));
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clockIn, clockOut, ...deps]);

  return state;
}
