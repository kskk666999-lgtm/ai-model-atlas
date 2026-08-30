import { describe, expect, it } from 'vitest';
import { resolveStaticUrl } from '@/lib/api';

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
