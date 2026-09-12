import { beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadBlob, downloadJson, readJsonFile } from './fileService';

describe('fileService', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it('downloads blobs through a temporary anchor', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:test');
    const revokeObjectURL = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);

    downloadBlob(new Blob(['demo']), 'demo.txt');

    expect(createObjectURL).toHaveBeenCalledOnce();
    expect(click).toHaveBeenCalledOnce();
    expect(document.querySelector('a')).toBeNull();
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test');
  });

  it('serializes JSON downloads', () => {
    const createObjectURL = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:json');
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);

    downloadJson({ ok: true }, 'config.json');

    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toBe('application/json');
  });

  it('reads JSON files', async () => {
    const file = new File([JSON.stringify({ imported: true })], 'config.json', { type: 'application/json' });
    await expect(readJsonFile<{ imported: boolean }>(file)).resolves.toEqual({ imported: true });
  });
});
