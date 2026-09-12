import { create } from 'zustand';

interface UIState {
  collapsed: boolean;
  setCollapsed: (collapsed: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  collapsed: false,
  setCollapsed: (collapsed) => set({ collapsed })
}));
