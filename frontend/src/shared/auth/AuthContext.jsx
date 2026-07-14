import { useMemo, useState } from "react";
import { AuthContext } from "./authContextValue";
import { clearStoredUser, getStoredUser, saveStoredUser } from "./storage";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getStoredUser());

  const value = useMemo(() => {
    const role = user?.role || user?.userType || null;

    return {
      user,
      role,
      login(nextUser) {
        saveStoredUser(nextUser);
        setUser(nextUser);
      },
      logout() {
        clearStoredUser();
        setUser(null);
      },
    };
  }, [user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
