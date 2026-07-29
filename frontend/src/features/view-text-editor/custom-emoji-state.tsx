import { createContext, useContext, type ReactNode } from "react";

import type {
  CustomEmojiCapabilityResult,
  ResolvedCustomEmoji,
} from "../../studio/api";

export const CUSTOM_EMOJI_RESOLVE_BATCH_SIZE = 200;
const CAPABILITY_STORAGE_VERSION = 1 as const;
const CAPABILITY_VALUES = new Set(["unknown", "available", "unavailable", "test-required"]);

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export type CustomEmojiReference = {
  id: string;
  fallback: string;
};

export type CustomEmojiBatchResolutionResult = {
  items: ResolvedCustomEmoji[];
  failures: Array<{ reference: CustomEmojiReference; error: unknown }>;
};

export type CustomEmojiDisplayStatus = "loading" | "resolved" | "fallback" | "unavailable";

export type CustomEmojiDisplayState = {
  id: string;
  fallback: string;
  status: CustomEmojiDisplayStatus;
  reason?: string;
  preview?: ResolvedCustomEmoji["preview"];
  previewUrl?: string;
};

export type CustomEmojiCapabilitySnapshot = CustomEmojiCapabilityResult & {
  customEmojiId: string;
  checkedAt: string;
};

export type CustomEmojiEditorAdapter = {
  states: Readonly<Record<string, CustomEmojiDisplayState>>;
  capability: CustomEmojiCapabilitySnapshot | null;
  resolve(id: string, fallback: string): Promise<CustomEmojiDisplayState>;
  resolveMany(references: readonly CustomEmojiReference[]): Promise<CustomEmojiDisplayState[]>;
  markPreviewUnavailable(id: string, reason?: string): void;
  testCapability(
    id: string,
    fallback: string,
    chatId: string,
  ): Promise<CustomEmojiCapabilityResult>;
};

type CustomEmojiResolveClient = {
  resolveCustomEmojis(
    projectId: string,
    ids: string[],
    fallbackById?: Record<string, string>,
  ): Promise<{ items: ResolvedCustomEmoji[] }>;
};

const CustomEmojiStateContext = createContext<CustomEmojiEditorAdapter | undefined>(undefined);

export function CustomEmojiStateProvider({
  adapter,
  children,
}: {
  adapter?: CustomEmojiEditorAdapter;
  children: ReactNode;
}) {
  return <CustomEmojiStateContext.Provider value={adapter}>{children}</CustomEmojiStateContext.Provider>;
}

export function useCustomEmojiState(id: string): {
  adapter?: CustomEmojiEditorAdapter;
  state?: CustomEmojiDisplayState;
} {
  const adapter = useContext(CustomEmojiStateContext);
  return { adapter, state: adapter?.states[id] };
}

export function CustomEmojiMedia({
  id,
  fallback,
  className = "",
}: {
  id: string;
  fallback: string;
  className?: string;
}) {
  const { adapter, state } = useCustomEmojiState(id);
  const status = state?.status ?? "fallback";
  const preview = status === "resolved" ? state?.preview : undefined;
  const previewUrl = status === "resolved" ? state?.previewUrl : undefined;
  const format = preview?.format;
  const title = customEmojiStatusLabel(state, fallback);
  const markUnavailable = () => adapter?.markPreviewUnavailable(id, "preview-load-failed");

  return (
    <span
      className={`view-rich-custom-emoji-media ${className}`.trim()}
      data-custom-emoji-state={status}
      data-custom-emoji-format={format}
      aria-label={title}
      title={title}
    >
      {preview && preview.format === "webp" && previewUrl ? (
        <img
          key={`${id}-${preview.loadedAt}`}
          src={previewUrl}
          alt=""
          decoding="async"
          onError={markUnavailable}
        />
      ) : null}
      {preview && preview.format === "webm" && previewUrl ? (
        <video
          key={`${id}-${preview.loadedAt}`}
          src={previewUrl}
          aria-hidden="true"
          autoPlay
          loop
          muted
          playsInline
          preload="metadata"
          onError={markUnavailable}
        />
      ) : null}
      <span className="view-rich-custom-emoji-media__fallback" aria-hidden="true">{fallback}</span>
      {format === "tgs" ? <span className="view-rich-custom-emoji-media__badge" aria-hidden="true">TGS</span> : null}
      {status === "loading" ? <span className="view-rich-custom-emoji-media__badge is-loading" aria-hidden="true">…</span> : null}
      {status === "unavailable" ? <span className="view-rich-custom-emoji-media__badge is-unavailable" aria-hidden="true">!</span> : null}
    </span>
  );
}

export async function resolveCustomEmojiBatches(
  client: CustomEmojiResolveClient,
  projectId: string,
  references: readonly CustomEmojiReference[],
): Promise<CustomEmojiBatchResolutionResult> {
  const unique = dedupeCustomEmojiReferences(references);
  const batches: CustomEmojiReference[][] = [];
  for (let index = 0; index < unique.length; index += CUSTOM_EMOJI_RESOLVE_BATCH_SIZE) {
    batches.push(unique.slice(index, index + CUSTOM_EMOJI_RESOLVE_BATCH_SIZE));
  }
  const responses = await Promise.allSettled(batches.map((batch) => client.resolveCustomEmojis(
    projectId,
    batch.map((item) => item.id),
    Object.fromEntries(batch.map((item) => [item.id, item.fallback])),
  )));
  const resolvedById = new Map<string, ResolvedCustomEmoji>();
  const failures: CustomEmojiBatchResolutionResult["failures"] = [];
  responses.forEach((response, index) => {
    if (response.status === "fulfilled") {
      response.value.items.forEach((item) => resolvedById.set(item.id, item));
      return;
    }
    batches[index].forEach((reference) => failures.push({ reference, error: response.reason }));
  });
  const items = unique.flatMap((reference) => {
    const item = resolvedById.get(reference.id);
    return item ? [item] : [];
  });
  return { items, failures };
}

export function loadingCustomEmojiState(reference: CustomEmojiReference): CustomEmojiDisplayState {
  return { ...reference, status: "loading" };
}

export function unavailableCustomEmojiState(
  reference: CustomEmojiReference,
  reason = "custom-emoji-unavailable",
): CustomEmojiDisplayState {
  return { ...reference, status: "unavailable", reason };
}

export function displayStateFromResolvedCustomEmoji(
  item: ResolvedCustomEmoji,
  fallback: string,
  previewUrl: (id: string) => string,
): CustomEmojiDisplayState {
  const normalizedFallback = item.fallbackEmoji || fallback;
  if (item.status === "resolved" && item.preview) {
    const baseUrl = previewUrl(item.id);
    const delimiter = baseUrl.includes("?") ? "&" : "?";
    return {
      id: item.id,
      fallback: normalizedFallback,
      status: "resolved",
      reason: item.reason,
      preview: item.preview,
      previewUrl: `${baseUrl}${delimiter}v=${encodeURIComponent(item.preview.loadedAt)}`,
    };
  }
  return {
    id: item.id,
    fallback: normalizedFallback,
    status: item.status === "unavailable" ? "unavailable" : "fallback",
    reason: item.reason ?? (item.status === "resolved" ? "preview-metadata-missing" : undefined),
  };
}

export function loadCustomEmojiCapability(
  storage: StorageLike | null | undefined,
  projectId: string,
): CustomEmojiCapabilitySnapshot | null {
  if (!storage) return null;
  try {
    const parsed = JSON.parse(storage.getItem(customEmojiCapabilityStorageKey(projectId)) ?? "null") as {
      v?: unknown;
      capability?: unknown;
      reason?: unknown;
      customEmojiId?: unknown;
      checkedAt?: unknown;
    } | null;
    if (!parsed
      || parsed.v !== CAPABILITY_STORAGE_VERSION
      || typeof parsed.capability !== "string"
      || !CAPABILITY_VALUES.has(parsed.capability)
      || typeof parsed.customEmojiId !== "string"
      || !/^\d+$/.test(parsed.customEmojiId)
      || typeof parsed.checkedAt !== "string"
      || !Number.isFinite(Date.parse(parsed.checkedAt))) return null;
    return {
      capability: parsed.capability as CustomEmojiCapabilityResult["capability"],
      ...(typeof parsed.reason === "string" ? { reason: parsed.reason } : {}),
      customEmojiId: parsed.customEmojiId,
      checkedAt: parsed.checkedAt,
    };
  } catch {
    return null;
  }
}

export function saveCustomEmojiCapability(
  storage: StorageLike | null | undefined,
  projectId: string,
  snapshot: CustomEmojiCapabilitySnapshot,
): void {
  if (!storage) return;
  try {
    storage.setItem(customEmojiCapabilityStorageKey(projectId), JSON.stringify({
      v: CAPABILITY_STORAGE_VERSION,
      capability: snapshot.capability,
      ...(snapshot.reason ? { reason: snapshot.reason } : {}),
      customEmojiId: snapshot.customEmojiId,
      checkedAt: snapshot.checkedAt,
    }));
  } catch {
    // Capability persistence is an enhancement; editor availability is unaffected.
  }
}

export function customEmojiCapabilityStorageKey(projectId: string): string {
  return `botstudio.rich-editor.custom-emoji-capability.v1:${encodeURIComponent(projectId)}`;
}

function dedupeCustomEmojiReferences(
  references: readonly CustomEmojiReference[],
): CustomEmojiReference[] {
  const byId = new Map<string, CustomEmojiReference>();
  references.forEach((reference) => {
    if (!byId.has(reference.id)) byId.set(reference.id, reference);
    else byId.set(reference.id, { ...reference });
  });
  return [...byId.values()];
}

function customEmojiStatusLabel(state: CustomEmojiDisplayState | undefined, fallback: string): string {
  if (!state) return `Custom emoji ${fallback}; preview not loaded.`;
  if (state.status === "loading") return `Custom emoji ${fallback}; loading Telegram preview.`;
  if (state.status === "unavailable") return `Custom emoji ${fallback}; preview unavailable${state.reason ? `: ${state.reason}` : "."}`;
  if (state.status === "fallback") return `Custom emoji ${fallback}; showing fallback${state.reason ? `: ${state.reason}` : "."}`;
  if (state.preview?.format === "tgs") return `Custom emoji ${fallback}; animated TGS preview is available in Telegram. Studio shows the fallback.`;
  if (state.preview?.format === "webm") return `Custom emoji ${fallback}; animated WebM preview loaded.`;
  return `Custom emoji ${fallback}; preview loaded.`;
}
