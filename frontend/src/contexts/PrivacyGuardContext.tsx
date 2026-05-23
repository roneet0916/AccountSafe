// src/contexts/PrivacyGuardContext.tsx

import React, { createContext, useState, useEffect, useContext, ReactNode, useCallback } from 'react';

interface PrivacyGuardContextType {
  isBlurred: boolean;
  enablePrivacyBlur: boolean;
  togglePrivacyBlur: () => void;
  setEnablePrivacyBlur: (enabled: boolean) => void;
}

const PrivacyGuardContext = createContext<PrivacyGuardContextType | undefined>(undefined);

export const PrivacyGuardProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // Store user preference in localStorage and keep it synced across tabs
  const [enablePrivacyBlur, setEnablePrivacyBlurState] = useState<boolean>(true);

  // Active blur state
  const [isBlurred, setIsBlurred] = useState<boolean>(false);

  // Basic auth presence check using localStorage, kept in sync with storage events
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return Boolean(localStorage.getItem('authToken'));
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const saved = localStorage.getItem('enablePrivacyBlur');
    if (saved !== null) {
      try {
        setEnablePrivacyBlurState(JSON.parse(saved));
      } catch {
        setEnablePrivacyBlurState(true);
      }
    }
  }, []);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === 'enablePrivacyBlur') {
        if (event.newValue !== null) {
          try {
            setEnablePrivacyBlurState(JSON.parse(event.newValue));
          } catch {
            setEnablePrivacyBlurState(true);
          }
        }
      }

      if (event.key === 'authToken') {
        setIsAuthenticated(Boolean(event.newValue));
      }
    };

    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  const syncEnablePrivacyBlur = useCallback((enabled: boolean) => {
    setEnablePrivacyBlurState(enabled);
    localStorage.setItem('enablePrivacyBlur', JSON.stringify(enabled));
  }, []);

  // Toggle preference
  const togglePrivacyBlur = useCallback(() => {
    setEnablePrivacyBlurState(prev => {
      const newValue = !prev;
      localStorage.setItem('enablePrivacyBlur', JSON.stringify(newValue));
      return newValue;
    });
  }, []);

  // Set preference directly
  const setEnablePrivacyBlur = useCallback((enabled: boolean) => {
    syncEnablePrivacyBlur(enabled);
  }, [syncEnablePrivacyBlur]);

  // Consolidated security check function
  const checkSecurity = useCallback(() => {
    if (!enablePrivacyBlur || !isAuthenticated) {
      setIsBlurred(false);
      return;
    }

    // Aggressive check: Blur if EITHER condition is true
    const shouldBlur = document.hidden || !document.hasFocus();
    setIsBlurred(shouldBlur);
  }, [enablePrivacyBlur, isAuthenticated]);

  // Handle all visibility/focus events
  useEffect(() => {
    if (!enablePrivacyBlur || !isAuthenticated) {
      setIsBlurred(false);
      return;
    }

    // Initial check on mount (handles background app opening)
    checkSecurity();

    // Event listeners for all scenarios
    const handleVisibilityChange = () => {
      if (!isAuthenticated) return;

      if (document.hidden) {
        setIsBlurred(true);
      } else {
        // Small delay to prevent flash on rapid tab switching
        setTimeout(() => {
          checkSecurity();
        }, 100);
      }
    };

    const handleWindowBlur = () => {
      // Triggered on Alt-Tab, clicking outside, etc.
      if (isAuthenticated) {
        setIsBlurred(true);
      }
    };

    const handleWindowFocus = () => {
      // Keep auth state up to date when the user returns to the window.
      setIsAuthenticated(Boolean(localStorage.getItem('authToken')));
      setTimeout(() => {
        checkSecurity();
      }, 100);
    };

    // Register all event listeners
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('blur', handleWindowBlur);
    window.addEventListener('focus', handleWindowFocus);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('blur', handleWindowBlur);
      window.removeEventListener('focus', handleWindowFocus);
    };
  }, [enablePrivacyBlur, isAuthenticated, checkSecurity]);

  return (
    <PrivacyGuardContext.Provider value={{ 
      isBlurred, 
      enablePrivacyBlur, 
      togglePrivacyBlur,
      setEnablePrivacyBlur 
    }}>
      {children}
    </PrivacyGuardContext.Provider>
  );
};

export const usePrivacyGuard = () => {
  const context = useContext(PrivacyGuardContext);
  if (context === undefined) {
    throw new Error('usePrivacyGuard must be used within a PrivacyGuardProvider');
  }
  return context;
};