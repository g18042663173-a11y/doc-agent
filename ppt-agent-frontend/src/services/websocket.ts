import type { ProgressResponse } from '@/types';

interface ProgressSocketOptions {
  onMessage: (data: ProgressResponse) => void;
  onError?: () => void;
  onClose?: () => void;
}

export function connectProgressSocket(taskId: string, options: ProgressSocketOptions): WebSocket {
  const apiBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';
  const wsBase = apiBase.replace(/^http/, 'ws').replace(/\/api$/, '');
  const socket = new WebSocket(`${wsBase}/api/generate/ws/${taskId}`);
  socket.onmessage = (event) => options.onMessage(JSON.parse(event.data));
  socket.onerror = () => options.onError?.();
  socket.onclose = () => options.onClose?.();
  return socket;
}
