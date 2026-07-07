import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { GUEST_ENABLED, getMe, type User } from "../../lib/api";
import { isGuestMode } from "../../lib/guestMode";

interface Props {
  children: ReactNode;
}

export default function AuthGate({ children }: Props) {
  const guest = GUEST_ENABLED && isGuestMode();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return (
      <main className="login-page">
        <p className="login-loading">Checking session…</p>
      </main>
    );
  }

  if (user === null) {
    if (guest) {
      return <>{children}</>;
    }
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
