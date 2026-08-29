import { createContext, useContext, useState, ReactNode } from 'react';

/** 图表主题钩子：本站为深色站点，主题切换用于未来扩展。 */
const ThemeContext = createContext<'dark' | 'light'>('dark');

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [theme] = useState<'dark' | 'light'>('dark');
  return <ThemeContext.Provider value={theme}>{children}</ThemeContext.Provider>;
}

export function useAppTheme() {
  return useContext(ThemeContext);
}
