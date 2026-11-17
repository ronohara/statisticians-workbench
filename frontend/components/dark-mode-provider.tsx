"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { useSession } from "next-auth/react";

interface DarkModeContextType {
  darkMode: boolean;
  setDarkMode: (value: boolean) => Promise<void>;
}

const DarkModeContext = createContext<DarkModeContextType | undefined>(undefined);

export function DarkModeProvider({ children }: { children: React.ReactNode }) {
  const { data: session, status } = useSession();
  const [darkMode, setDarkModeState] = useState<boolean>(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // Load dark mode preference from the database when user is authenticated
  useEffect(() => {
    if (status === "loading") return;
    if (!session) {
      // Not logged in: default to light mode
      document.documentElement.classList.remove("dark");
      setDarkModeState(false);
      setIsLoaded(true);
      return;
    }

    const fetchDarkMode = async () => {
      try {
        const res = await fetch("/api/user-settings");
        const data = await res.json();
        const dbDarkMode = data.darkMode ?? false;
        setDarkModeState(dbDarkMode);
        document.documentElement.classList.toggle("dark", dbDarkMode);
      } catch (error) {
        console.error("Failed to load dark mode preference:", error);
      } finally {
        setIsLoaded(true);
      }
    };
    fetchDarkMode();
  }, [session, status]);

  // Function to update dark mode (both UI and database)
  const setDarkMode = async (value: boolean) => {
    if (!session) return;
    setDarkModeState(value);
    document.documentElement.classList.toggle("dark", value);
    try {
      // Save to database via user-settings API
      await fetch("/api/user-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ darkMode: value }),
      });
    } catch (error) {
      console.error("Failed to save dark mode preference:", error);
    }
  };

  if (!isLoaded) {
    // Optionally show a loading indicator (or return null)
    return null;
  }

  return (
    <DarkModeContext.Provider value={{ darkMode, setDarkMode }}>
      {children}
    </DarkModeContext.Provider>
  );
}

export function useDarkMode() {
  const context = useContext(DarkModeContext);
  if (!context) throw new Error("useDarkMode must be used within DarkModeProvider");
  return context;
}