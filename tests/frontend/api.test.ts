import { describe, expect, it } from 'vitest';
import { resolveStaticUrl } from '@/lib/api';
import { fmtDate, fmtDateTime } from '@/lib/format';

describe('resolveStaticUrl', () => {
  it('keeps root deployment data URLs unchanged', () => {
    expect(resolveStaticUrl('/data/meta.json', '/')).toBe('/data/meta.json');
  });

  it('prefixes data URLs with the GitHub Pages project base', () => {
    expect(resolveStaticUrl('/data/meta.json', '/ai-model-atlas/')).toBe(
      '/ai-model-atlas/data/meta.json',
    );
  });

  it('normalizes a project base without a trailing slash', () => {
    expect(resolveStaticUrl('/data/models/index.json', '/ai-model-atlas')).toBe(
      '/ai-model-atlas/data/models/index.json',
    );
  });

  it('does not rewrite external URLs', () => {
    expect(resolveStaticUrl('https://example.test/data.json', '/ai-model-atlas/')).toBe(
      'https://example.test/data.json',
    );
  });
});

describe('date formatting', () => {
  it('formats compact upstream timestamps without truncating the day', () => {
    expect(fmtDate('20250917132916')).toBe('2025-09-17');
    expect(fmtDateTime('20250917132916')).toBe('2025-09-17 13:29');
  });
});
