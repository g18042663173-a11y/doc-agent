import { create } from 'zustand';
import type { ProgressResponse } from '@/types';

interface DocumentState {
  taskId: string | null;
  progress: ProgressResponse | null;
  setTaskId: (taskId: string | null) => void;
  setProgress: (progress: ProgressResponse | null) => void;
}

export const useDocumentStore = create<DocumentState>((set) => ({
  taskId: null,
  progress: null,
  setTaskId: (taskId) => set({ taskId }),
  setProgress: (progress) => set({ progress })
}));
