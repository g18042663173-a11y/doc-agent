import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { ColorScheme, TemplateConfig, UserConfig } from '@/types';

interface UserState {
  currentUser: UserConfig | null;
  users: UserConfig[];
  currentTemplate: TemplateConfig | null;
  currentColorScheme: ColorScheme | null;
  setUsers: (users: UserConfig[]) => void;
  setCurrentUser: (user: UserConfig | null) => void;
  setCurrentTemplate: (template: TemplateConfig | null) => void;
  setCurrentColorScheme: (scheme: ColorScheme | null) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      currentUser: null,
      users: [],
      currentTemplate: null,
      currentColorScheme: null,
      setUsers: (users) => set({ users }),
      setCurrentUser: (user) => set({ currentUser: user }),
      setCurrentTemplate: (template) => set({ currentTemplate: template }),
      setCurrentColorScheme: (scheme) => set({ currentColorScheme: scheme })
    }),
    {
      name: 'ppt-agent-user-storage'
    }
  )
);
