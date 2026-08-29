import { useEffect, useState } from 'react';

const cache = new Map<string, unknown>();

/** 测试用：清空模块级缓存。 */
export function clearCache() {
  cache.clear();
}

export function useJson<T>(url: string | null): { data: T | null; error: string | null; loading: boolean } {
  const [data, setData] = useState<T | null>(() => (url && cache.has(url) ? (cache.get(url) as T) : null));
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(() => !url || !cache.has(url));

  useEffect(() => {
    if (!url) return;
    let alive = true;
    if (cache.has(url)) {
      setData(cache.get(url) as T);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    fetch(url)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => {
        cache.set(url, json);
        if (alive) {
          setData(json);
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (alive) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [url]);

  return { data, error, loading };
}

export function useMeta() {
  const { data, error, loading } = useJson<import('@/types/data').Meta>('/data/meta.json');
  return { meta: data, error, loading };
}

/** 批量获取多个 JSON（内部使用 Promise.all，遵守 Hook 规则）。 */
export function useJsonMany<T>(urls: string[]): { data: Map<string, T>; loading: boolean; error: string | null } {
  const key = urls.join('|');
  const [data, setData] = useState<Map<string, T>>(new Map());
  const [loading, setLoading] = useState(urls.length > 0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!urls.length) {
      setData(new Map());
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all(
      urls.map(async (u) => {
        if (cache.has(u)) return [u, cache.get(u) as T] as const;
        const r = await fetch(u);
        if (!r.ok) throw new Error(`HTTP ${r.status} @ ${u}`);
        const json = (await r.json()) as T;
        cache.set(u, json);
        return [u, json] as const;
      }),
    )
      .then((entries) => {
        if (alive) {
          setData(new Map(entries));
          setLoading(false);
        }
      })
      .catch((e: unknown) => {
        if (alive) {
          setError(e instanceof Error ? e.message : String(e));
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { data, loading, error };
}
