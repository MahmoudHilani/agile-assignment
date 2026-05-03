"use client";

import { createContext, useCallback, useContext, useSyncExternalStore } from "react";

interface AdminAuthContextType {
  isAdmin: boolean;
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
}

const AdminAuthContext = createContext<AdminAuthContextType>({
  isAdmin: false,
  token: null,
  login: () => {},
  logout: () => {},
});

const ADMIN_TOKEN_KEY = "admin_token";

function getStoredToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ADMIN_TOKEN_KEY);
}

function subscribeToTokenChanges(onStoreChange: () => void) {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === ADMIN_TOKEN_KEY) {
      onStoreChange();
    }
  };

  window.addEventListener("storage", handleStorage);
  return () => window.removeEventListener("storage", handleStorage);
}

export function AdminAuthProvider({ children }: { children: React.ReactNode }) {
  const token = useSyncExternalStore(subscribeToTokenChanges, getStoredToken, () => null);

  const login = useCallback((newToken: string) => {
    localStorage.setItem(ADMIN_TOKEN_KEY, newToken);
    window.dispatchEvent(new StorageEvent("storage", { key: ADMIN_TOKEN_KEY, newValue: newToken }));
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    window.dispatchEvent(new StorageEvent("storage", { key: ADMIN_TOKEN_KEY, newValue: null }));
  }, []);

  return (
    <AdminAuthContext.Provider value={{ isAdmin: !!token, token, login, logout }}>
      {children}
    </AdminAuthContext.Provider>
  );
}

export const useAdminAuth = () => useContext(AdminAuthContext);
