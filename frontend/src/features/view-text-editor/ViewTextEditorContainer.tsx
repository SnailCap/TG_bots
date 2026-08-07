import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { BotContentDocument, ContentDiagnostic, TelegramCompileResult } from "../../domain/content";
import type { CustomEmojiCapabilityResult, ResolvedCustomEmoji, SendPreviewMessageResult, StudioApiClient } from "../../studio/api";
import { SYSTEM_CONTEXT_FIELDS, type ContextFieldDefinition } from "../template-composer/context-catalog";
import { useResourceVariableFields } from "../template-composer/use-resource-variable-fields";
import {
  displayStateFromResolvedCustomEmoji,
  loadCustomEmojiCapability,
  loadingCustomEmojiState,
  resolveCustomEmojiBatches,
  saveCustomEmojiCapability,
  unavailableCustomEmojiState,
  type CustomEmojiCapabilitySnapshot,
  type CustomEmojiDisplayState,
  type CustomEmojiEditorAdapter,
  type CustomEmojiReference,
} from "./custom-emoji-state";
import type { RichEditorPreviewValues } from "./TelegramCompiledPreview";
import type { RichEditorSaveState } from "./ViewTextEditor";
import {
  clearViewTextDraftDiscard,
  consumeViewTextDraftDiscard,
  contentDraftKey,
} from "./content-draft";

const RichTextEditor = lazy(async () => {
  const module = await import("./ViewTextEditor");
  return { default: module.ViewTextEditor };
});

const AUTOSAVE_DELAY_MS = 750;
const COMPILE_DELAY_MS = 250;
const DRAFT_SCHEMA_VERSION = 1;

type DraftEnvelope = {
  schemaVersion: typeof DRAFT_SCHEMA_VERSION;
  baseRevision: string;
  updatedAt: string;
  editorSessionId?: string;
  dirty?: boolean;
  document: BotContentDocument;
};

export type ViewTextEditorContainerProps = {
  api: {
    compileContent(
      projectId: string,
      document: BotContentDocument,
      variables?: Record<string, unknown>,
      signal?: AbortSignal,
    ): Promise<TelegramCompileResult>;
    resolveCustomEmojis(
      projectId: string,
      ids: string[],
      fallbackById?: Record<string, string>,
    ): Promise<{ items: ResolvedCustomEmoji[] }>;
    customEmojiPreviewUrl(projectId: string, id: string): string;
    testCustomEmojiCapability(
      projectId: string,
      id: string,
      chatId: number | string,
      fallbackEmoji?: string,
    ): Promise<CustomEmojiCapabilityResult>;
    sendPreviewMessage(projectId: string, input: {
      document: BotContentDocument;
      variables?: Record<string, unknown>;
      chatId: number | string;
      splitLongMessages?: boolean;
    }): Promise<SendPreviewMessageResult>;
    getVariables?: StudioApiClient["getVariables"];
  };
  projectId: string;
  projectRoot: string;
  viewId: string;
  baseRevision: string;
  document: BotContentDocument;
  version: number;
  savedVersion: number;
  dirty: boolean;
  busy: boolean;
  saving: boolean;
  saveError: boolean;
  onDocumentChange(document: BotContentDocument): void;
  onRequestSave(): void;
};

export function ViewTextEditorContainer({
  api,
  projectId,
  projectRoot,
  viewId,
  baseRevision,
  document,
  version,
  savedVersion,
  dirty,
  busy,
  saving,
  saveError,
  onDocumentChange,
  onRequestSave,
}: ViewTextEditorContainerProps) {
  const [compileResult, setCompileResult] = useState<TelegramCompileResult | null>(null);
  const [customEmojiStates, setCustomEmojiStates] = useState<Record<string, CustomEmojiDisplayState>>({});
  const [customEmojiCapability, setCustomEmojiCapability] = useState<CustomEmojiCapabilitySnapshot | null>(
    () => loadCustomEmojiCapability(safeLocalStorage(), projectId),
  );
  const variableApi = useMemo(
    () => api.getVariables ? { getVariables: api.getVariables.bind(api) } : undefined,
    [api],
  );
  const variableFields = useResourceVariableFields(variableApi, projectId, {
    resourceType: "view",
    resourceId: viewId,
  });
  const [previewValues, setPreviewValues] = useState<RichEditorPreviewValues>(() => defaultPreviewValues());
  useEffect(() => {
    setPreviewValues((current) => ({ ...defaultPreviewValues(variableFields), ...current }));
  }, [variableFields]);
  const [draftRecovered, setDraftRecovered] = useState(false);
  const draftKey = useMemo(() => contentDraftKey(projectRoot, viewId), [projectRoot, viewId]);
  const editorSessionId = useRef(createEditorSessionId());
  const customEmojis = useMemo(() => customEmojiReferences(document), [document]);
  const customEmojiKey = useMemo(() => JSON.stringify(customEmojis), [customEmojis]);
  const resolveCustomEmojiMany = useCallback(async (references: readonly CustomEmojiReference[]) => {
    const unique = [...new Map(references.map((reference) => [reference.id, reference])).values()];
    setCustomEmojiStates((current) => {
      const next = { ...current };
      unique.forEach((reference) => { next[reference.id] = loadingCustomEmojiState(reference); });
      return next;
    });
    try {
      const { items, failures } = await resolveCustomEmojiBatches(api, projectId, unique);
      const resolvedById = new Map(items.map((item) => [item.id, item]));
      const failedById = new Map(failures.map(({ reference, error }) => [
        reference.id,
        error instanceof Error ? error.message : "custom-emoji-resolution-failed",
      ]));
      const states = unique.map((reference) => {
        const item = resolvedById.get(reference.id);
        return item
          ? displayStateFromResolvedCustomEmoji(
            item,
            reference.fallback,
            (emojiId) => api.customEmojiPreviewUrl(projectId, emojiId),
          )
          : unavailableCustomEmojiState(reference, failedById.get(reference.id) ?? "not-found");
      });
      setCustomEmojiStates((current) => ({
        ...current,
        ...Object.fromEntries(states.map((state) => [state.id, state])),
      }));
      return states;
    } catch (error) {
      const reason = error instanceof Error ? error.message : "custom-emoji-resolution-failed";
      setCustomEmojiStates((current) => {
        const next = { ...current };
        unique.forEach((reference) => { next[reference.id] = unavailableCustomEmojiState(reference, reason); });
        return next;
      });
      throw error;
    }
  }, [api, projectId]);
  const resolveCustomEmoji = useCallback(async (id: string, fallback: string) => {
    const [state] = await resolveCustomEmojiMany([{ id, fallback }]);
    return state ?? unavailableCustomEmojiState({ id, fallback }, "not-found");
  }, [resolveCustomEmojiMany]);
  const markPreviewUnavailable = useCallback((id: string, reason = "preview-load-failed") => {
    setCustomEmojiStates((current) => {
      const state = current[id];
      if (!state || state.status !== "resolved") return current;
      return {
        ...current,
        [id]: unavailableCustomEmojiState({ id, fallback: state.fallback }, reason),
      };
    });
  }, []);
  const testCustomEmojiCapability = useCallback(async (id: string, fallback: string, chatId: string) => {
    const result = await api.testCustomEmojiCapability(projectId, id, chatId, fallback);
    const snapshot: CustomEmojiCapabilitySnapshot = {
      ...result,
      customEmojiId: id,
      checkedAt: new Date().toISOString(),
    };
    saveCustomEmojiCapability(safeLocalStorage(), projectId, snapshot);
    setCustomEmojiCapability(snapshot);
    return result;
  }, [api, projectId]);
  const customEmojiAdapter = useMemo<CustomEmojiEditorAdapter>(() => ({
    states: customEmojiStates,
    capability: customEmojiCapability,
    resolve: resolveCustomEmoji,
    resolveMany: resolveCustomEmojiMany,
    markPreviewUnavailable,
    testCapability: testCustomEmojiCapability,
  }), [
    customEmojiCapability,
    customEmojiStates,
    markPreviewUnavailable,
    resolveCustomEmoji,
    resolveCustomEmojiMany,
    testCustomEmojiCapability,
  ]);
  const emojiWarnings = useMemo(
    () => customEmojiDiagnostics(customEmojis, customEmojiStates, customEmojiCapability),
    [customEmojiCapability, customEmojiKey, customEmojiStates],
  );
  const latestRef = useRef({ document, dirty, baseRevision });
  const saveRef = useRef(onRequestSave);
  const attemptedVersionRef = useRef<number | null>(null);
  latestRef.current = { document, dirty, baseRevision };
  saveRef.current = onRequestSave;

  useEffect(() => {
    setCustomEmojiStates({});
    setCustomEmojiCapability(loadCustomEmojiCapability(safeLocalStorage(), projectId));
  }, [projectId]);

  useEffect(() => {
    clearViewTextDraftDiscard(draftKey);
    const recovered = readDraft(draftKey, viewId, baseRevision);
    if (!recovered || sameDocument(recovered.document, document)) return;
    setDraftRecovered(true);
    onDocumentChange(recovered.document);
    // Recovery is intentionally one-shot for this mounted editor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey]);

  useEffect(() => {
    if (dirty) writeDraft(draftKey, baseRevision, document, editorSessionId.current);
    else if (version === savedVersion) removeDraft(draftKey);
  }, [baseRevision, dirty, document, draftKey, savedVersion, version]);

  useEffect(() => {
    if (draftRecovered && !dirty && version === savedVersion) setDraftRecovered(false);
  }, [dirty, draftRecovered, savedVersion, version]);

  useEffect(() => {
    const flushDraft = () => {
      const latest = latestRef.current;
      if (latest.dirty) writeDraft(draftKey, latest.baseRevision, latest.document, editorSessionId.current);
    };
    window.addEventListener("beforeunload", flushDraft);
    return () => {
      window.removeEventListener("beforeunload", flushDraft);
      if (consumeViewTextDraftDiscard(draftKey)) return;
      flushDraft();
    };
  }, [draftKey]);

  useEffect(() => {
    if (!dirty || saving || busy || attemptedVersionRef.current === version) return;
    const timer = window.setTimeout(() => {
      attemptedVersionRef.current = version;
      saveRef.current();
    }, AUTOSAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [busy, dirty, saving, version]);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void api.compileContent(
        projectId,
        document,
        nestedPreviewValues(previewValues),
        controller.signal,
      ).then(setCompileResult).catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setCompileResult({
          messages: [],
          warnings: [],
          errors: [{
            severity: "error",
            code: "preview_compile_failed",
            message: error instanceof Error ? error.message : "Preview compilation failed.",
          }],
        });
      });
    }, COMPILE_DELAY_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [api, document, previewValues, projectId]);

  useEffect(() => {
    if (!customEmojis.length) return;
    let active = true;
    setCustomEmojiStates((current) => {
      const next = { ...current };
      customEmojis.forEach((reference) => { next[reference.id] = loadingCustomEmojiState(reference); });
      return next;
    });
    void resolveCustomEmojiBatches(api, projectId, customEmojis)
      .then(({ items, failures }) => {
        if (!active) return;
        const resolvedById = new Map(items.map((item) => [item.id, item]));
        const failedById = new Map(failures.map(({ reference, error }) => [
          reference.id,
          error instanceof Error ? error.message : "custom-emoji-resolution-failed",
        ]));
        setCustomEmojiStates((current) => {
          const next = { ...current };
          customEmojis.forEach((reference) => {
            const item = resolvedById.get(reference.id);
            next[reference.id] = item
              ? displayStateFromResolvedCustomEmoji(
                item,
                reference.fallback,
                (id) => api.customEmojiPreviewUrl(projectId, id),
              )
              : unavailableCustomEmojiState(reference, failedById.get(reference.id) ?? "not-found");
          });
          return next;
        });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const reason = error instanceof Error ? error.message : "custom-emoji-resolution-failed";
        setCustomEmojiStates((current) => {
          const next = { ...current };
          customEmojis.forEach((reference) => { next[reference.id] = unavailableCustomEmojiState(reference, reason); });
          return next;
        });
      });
    return () => { active = false; };
    // The serialized key keeps metadata requests independent from normal typing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, customEmojiKey, projectId]);

  const saveState: RichEditorSaveState = saving
    ? "saving"
    : saveError && dirty
      ? "error"
      : dirty
        ? "dirty"
        : savedVersion > 0
          ? "saved"
          : "idle";

  return (
    <div className="view-text-editor-container">
      {draftRecovered ? (
        <div className="view-rich-editor__recovery" role="status">
          Recovered a newer local draft. It will be saved after validation.
        </div>
      ) : null}
      <Suspense fallback={<div className="view-rich-editor__boot" role="status">Loading rich editor…</div>}>
        <RichTextEditor
          variableFields={variableFields}
          document={document}
          compileResult={compileResult ? {
            ...compileResult,
            warnings: [...compileResult.warnings, ...emojiWarnings],
          } : compileResult}
          previewValues={previewValues}
          saveState={saveState}
          onDocumentChange={(next) => {
            attemptedVersionRef.current = null;
            setDraftRecovered(false);
            writeDraft(draftKey, baseRevision, next, editorSessionId.current);
            onDocumentChange(next);
          }}
          onPreviewValuesChange={setPreviewValues}
          onSendPreview={(chatId) => api.sendPreviewMessage(projectId, {
            document,
            variables: nestedPreviewValues(previewValues),
            chatId,
            splitLongMessages: true,
          })}
          customEmojiAdapter={customEmojiAdapter}
          onSaveRetry={() => {
            attemptedVersionRef.current = null;
            saveRef.current();
          }}
        />
      </Suspense>
    </div>
  );
}

function customEmojiReferences(document: BotContentDocument): Array<{ id: string; fallback: string }> {
  const values = new Map<string, string>();
  for (const block of document.content) {
    if (block.type === "codeBlock" || block.type === "legacyTemplate") continue;
    for (const node of block.content) {
      if (node.type === "customEmoji") values.set(node.customEmojiId, node.fallbackEmoji);
    }
  }
  return [...values].map(([id, fallback]) => ({ id, fallback }));
}

export function nestedPreviewValues(values: RichEditorPreviewValues): Record<string, unknown> {
  const root: Record<string, unknown> = {};
  for (const [path, value] of Object.entries(values)) {
    const parts = path.split(".").filter(Boolean);
    if (!parts.length) continue;
    let cursor = root;
    parts.forEach((part, index) => {
      if (index === parts.length - 1) {
        cursor[part] = value;
        return;
      }
      const existing = cursor[part];
      if (!existing || typeof existing !== "object" || Array.isArray(existing)) {
        cursor[part] = {};
      }
      cursor = cursor[part] as Record<string, unknown>;
    });
  }
  return root;
}

function defaultPreviewValues(
  fields: readonly ContextFieldDefinition[] = SYSTEM_CONTEXT_FIELDS,
): RichEditorPreviewValues {
  return Object.fromEntries(fields.map((field) => [field.path, field.example ?? ""]));
}

function readDraft(key: string, viewId: string, baseRevision: string): DraftEnvelope | null {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<DraftEnvelope>;
    if (parsed.schemaVersion !== DRAFT_SCHEMA_VERSION
      || parsed.baseRevision !== baseRevision
      || !parsed.document
      || parsed.document.schemaVersion !== 1
      || parsed.document.id !== viewId
      || !Array.isArray(parsed.document.content)) return null;
    return parsed as DraftEnvelope;
  } catch {
    return null;
  }
}

function writeDraft(
  key: string,
  baseRevision: string,
  document: BotContentDocument,
  editorSessionId: string,
): void {
  try {
    const envelope: DraftEnvelope = {
      schemaVersion: DRAFT_SCHEMA_VERSION,
      baseRevision,
      updatedAt: new Date().toISOString(),
      editorSessionId,
      dirty: true,
      document,
    };
    window.localStorage.setItem(key, JSON.stringify(envelope));
  } catch {
    // Draft persistence is best-effort. The in-memory tab remains canonical.
  }
}

function createEditorSessionId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `session-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  }
}

function removeDraft(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Storage can be disabled by the host; saving to project files still works.
  }
}

function sameDocument(left: BotContentDocument, right: BotContentDocument): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function customEmojiDiagnostics(
  references: readonly { id: string; fallback: string }[],
  states: Readonly<Record<string, CustomEmojiDisplayState>>,
  capability: CustomEmojiCapabilitySnapshot | null,
): ContentDiagnostic[] {
  if (!references.length) return [];
  const warnings = references.flatMap((reference): ContentDiagnostic[] => {
    const state = states[reference.id];
    if (!state || state.status === "loading" || state.status === "resolved") return [];
    return [{
      severity: "warning",
      code: state.reason && /^[a-z0-9_-]+$/i.test(state.reason)
        ? state.reason
        : "custom_emoji_resolution_failed",
      message: `Custom emoji ${reference.id} uses its fallback because its Telegram preview is unavailable.`,
    }];
  });
  if (!capability || capability.capability === "unknown" || capability.capability === "test-required") {
    warnings.push({
      severity: "warning",
      code: "custom_emoji_capability_unknown",
      message: "This bot's custom emoji capability has not been verified. Use the explicit capability test in the emoji picker.",
    });
  } else if (capability.capability === "unavailable") {
    warnings.push({
      severity: "warning",
      code: "custom_emoji_capability_unavailable",
      message: "The latest capability test indicates that this bot cannot send custom emoji.",
    });
  }
  return warnings;
}

function safeLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
