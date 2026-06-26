import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface SessionToolbarContextValue {
  content: ReactNode;
  setContent: (content: ReactNode) => void;
}

const SessionToolbarContext = createContext<SessionToolbarContextValue | null>(null);

export function SessionToolbarProvider({ children }: { children: ReactNode }) {
  const [content, setContent] = useState<ReactNode>(null);
  const value = useMemo(
    () => ({
      content,
      setContent,
    }),
    [content],
  );

  return (
    <SessionToolbarContext.Provider value={value}>
      {children}
    </SessionToolbarContext.Provider>
  );
}

export function useSessionToolbarContent() {
  return useContext(SessionToolbarContext)?.content ?? null;
}

/** Mount board tools into the session topbar center slot. */
export function useRegisterSessionToolbar(content: ReactNode) {
  const ctx = useContext(SessionToolbarContext);

  useEffect(() => {
    if (!ctx) {
      return;
    }
    ctx.setContent(content);
    return () => {
      ctx.setContent(null);
    };
  }, [ctx, content]);
}
