const DRAFT_KEY_PREFIX = "botstudio:content-draft:v1";

// A confirmed discard happens in the Studio controller immediately before the
// editor unmounts. The marker lets the unmount cleanup distinguish that path
// from a crash/navigation close, where flushing the latest draft is required.
const discardedDraftKeys = new Set<string>();

export function contentDraftKey(projectRoot: string, viewId: string): string {
  return `${DRAFT_KEY_PREFIX}:${encodeURIComponent(projectRoot)}:${encodeURIComponent(viewId)}`;
}

export function discardViewTextDraft(projectRoot: string, viewId: string): void {
  const key = contentDraftKey(projectRoot, viewId);
  discardedDraftKeys.add(key);
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Project-file saving remains available when browser storage is disabled.
  }
}

export function consumeViewTextDraftDiscard(key: string): boolean {
  const discarded = discardedDraftKeys.has(key);
  discardedDraftKeys.delete(key);
  return discarded;
}

export function clearViewTextDraftDiscard(key: string): void {
  discardedDraftKeys.delete(key);
}
