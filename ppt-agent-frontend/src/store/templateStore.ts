import { create } from 'zustand';
import type { ColorScheme, TemplateConfig } from '@/types';

interface TemplateState {
  templates: TemplateConfig[];
  colorSchemes: ColorScheme[];
  setTemplates: (templates: TemplateConfig[]) => void;
  setColorSchemes: (schemes: ColorScheme[]) => void;
}

export const useTemplateStore = create<TemplateState>((set) => ({
  templates: [],
  colorSchemes: [],
  setTemplates: (templates) => set({ templates }),
  setColorSchemes: (colorSchemes) => set({ colorSchemes })
}));
