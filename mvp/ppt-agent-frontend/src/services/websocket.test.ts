import { describe, expect, it, vi } from 'vitest';
import { connectProgressSocket } from './websocket';

class MockWebSocket {
  url: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
  }
}

describe('connectProgressSocket', () => {
  it('connects to the task WebSocket and forwards events', () => {
    vi.stubGlobal('WebSocket', MockWebSocket);
    const onMessage = vi.fn();
    const onError = vi.fn();
    const onClose = vi.fn();

    const socket = connectProgressSocket('task-1', { onMessage, onError, onClose }) as unknown as MockWebSocket;

    expect(socket.url).toBe('ws://127.0.0.1:8000/api/generate/ws/task-1');
    socket.onmessage?.({ data: JSON.stringify({ task_id: 'task-1', status: 'completed', progress: 100, current_step: 'done' }) } as MessageEvent);
    socket.onerror?.();
    socket.onclose?.();

    expect(onMessage).toHaveBeenCalledWith({ task_id: 'task-1', status: 'completed', progress: 100, current_step: 'done' });
    expect(onError).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });
});
