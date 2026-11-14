import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import { ApiError, api, errorMessage, setCsrfToken } from "./api";
import type { Session } from "./api";

interface AuthValue {
  session: Session | null;
  loading: boolean;
  error: string | null;
  needsBootstrap: boolean;
  webBootstrapAllowed: boolean;
  demoEnabled: boolean;
  login: (email: string, password: string) => Promise<void>;
  bootstrap: (email: string, displayName: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsBootstrap, setNeedsBootstrap] = useState(false);
  const [webBootstrapAllowed, setWebBootstrapAllowed] = useState(true);
  const [demoEnabled, setDemoEnabled] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const status = await api<{
        needs_bootstrap: boolean;
        web_bootstrap_allowed: boolean;
        demo_enabled: boolean;
      }>("/api/system/bootstrap");
      setNeedsBootstrap(status.needs_bootstrap);
      setWebBootstrapAllowed(status.web_bootstrap_allowed);
      setDemoEnabled(status.demo_enabled);
      try {
        const current = await api<Session>("/api/auth/session");
        setSession(current);
        setCsrfToken(current.csrf_token);
        setError(null);
      } catch (caught) {
        if (caught instanceof ApiError && caught.status === 401) {
          setSession(null);
          setCsrfToken(null);
        } else {
          setError(errorMessage(caught));
        }
      }
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const handler = () => {
      setSession(null);
      setCsrfToken(null);
    };
    window.addEventListener("buktirilis:unauthorized", handler);
    return () => window.removeEventListener("buktirilis:unauthorized", handler);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const current = await api<Session>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setSession(current);
    setCsrfToken(current.csrf_token);
    setNeedsBootstrap(false);
    setError(null);
  }, []);

  const bootstrap = useCallback(
    async (email: string, displayName: string, password: string) => {
      const current = await api<Session>("/api/auth/bootstrap", {
        method: "POST",
        body: JSON.stringify({ email, display_name: displayName, password }),
      });
      setSession(current);
      setCsrfToken(current.csrf_token);
      setNeedsBootstrap(false);
      setError(null);
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } finally {
      setSession(null);
      setCsrfToken(null);
    }
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      session,
      loading,
      error,
      needsBootstrap,
      webBootstrapAllowed,
      demoEnabled,
      login,
      bootstrap,
      logout,
      refresh,
    }),
    [
      session,
      loading,
      error,
      needsBootstrap,
      webBootstrapAllowed,
      demoEnabled,
      login,
      bootstrap,
      logout,
      refresh,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

interface ApiData<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
  refresh: () => void;
  setData: (value: T | null) => void;
}

export function useApi<T>(
  path: string | null,
  options: { pollMs?: number } = {},
): ApiData<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [reloadKey, setReloadKey] = useState(0);
  const pathRef = useRef(path);
  pathRef.current = path;

  const refresh = useCallback(() => setReloadKey((key) => key + 1), []);

  useEffect(() => {
    if (!path) {
      setLoading(false);
      return;
    }
    let active = true;
    const controller = new AbortController();
    setLoading(true);
    api<T>(path, { signal: controller.signal })
      .then((payload) => {
        if (!active) return;
        setData(payload);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [path, reloadKey]);

  useEffect(() => {
    if (!options.pollMs || !path) return;
    const timer = window.setInterval(() => setReloadKey((key) => key + 1), options.pollMs);
    return () => window.clearInterval(timer);
  }, [options.pollMs, path]);

  return { data, error, loading, refresh, setData };
}
