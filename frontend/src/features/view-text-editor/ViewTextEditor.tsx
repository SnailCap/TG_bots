import { useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

import { sanitizePastedHtml } from "../template-composer/paste-sanitizer";
import { documentFromTiptapJson, documentToTiptapJson } from "./conversion";
import { EmojiPickerPopover, LinkEditorPopover, VariablePickerPopover } from "./EditorPopovers";
import { CustomEmojiStateProvider, type CustomEmojiEditorAdapter } from "./custom-emoji-state";
import {
  CustomEmojiNode,
  ExpandableBlockquote,
  InternalClipboard,
  LegacyTemplateNode,
  SpoilerMark,
  VariableNode,
} from "./extensions";
import {
  isSafeContentLink,
  validateBotContentDocument,
  type BotContentDocument,
  type TelegramCompileResult,
} from "./model";
import { RichTextToolbar } from "./RichTextToolbar";
import { SlashCommandMenu } from "./SlashCommandMenu";
import {
  TelegramCompiledPreview,
  type RichEditorPreviewValues,
  type SendPreviewResult,
} from "./TelegramCompiledPreview";
import "./view-text-editor.css";

export type RichEditorSaveState = "idle" | "dirty" | "saving" | "saved" | "error";

export type ViewTextEditorProps = {
  document: BotContentDocument;
  compileResult: TelegramCompileResult | null;
  previewValues: RichEditorPreviewValues;
  saveState: RichEditorSaveState;
  onDocumentChange(document: BotContentDocument): void;
  onPreviewValuesChange(values: RichEditorPreviewValues): void;
  onSendPreview?(chatId: string): Promise<SendPreviewResult>;
  onSaveRetry?(): void;
  customEmojiAdapter?: CustomEmojiEditorAdapter;
};

type OpenPanel = "variables" | "emoji" | "link" | null;

export function ViewTextEditor({
  document,
  compileResult,
  previewValues,
  saveState,
  onDocumentChange,
  onPreviewValuesChange,
  onSendPreview,
  onSaveRetry,
  customEmojiAdapter,
}: ViewTextEditorProps) {
  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  const documentRef = useRef(document);
  const onDocumentChangeRef = useRef(onDocumentChange);
  documentRef.current = document;
  onDocumentChangeRef.current = onDocumentChange;

  const extensions = useMemo(() => [
    StarterKit.configure({
      heading: false,
      bulletList: false,
      orderedList: false,
      listItem: false,
      listKeymap: false,
      horizontalRule: false,
      trailingNode: false,
      link: {
        autolink: false,
        linkOnPaste: false,
        openOnClick: false,
        enableClickSelection: true,
        isAllowedUri: isSafeContentLink,
        HTMLAttributes: { rel: "noopener noreferrer" },
      },
      blockquote: { HTMLAttributes: { class: "view-rich-editor__quote" } },
      codeBlock: { HTMLAttributes: { class: "view-rich-editor__code-block" } },
    }),
    SpoilerMark,
    VariableNode,
    CustomEmojiNode,
    ExpandableBlockquote,
    LegacyTemplateNode,
    InternalClipboard,
  ], []);

  const editor = useEditor({
    extensions,
    content: documentToTiptapJson(document),
    editorProps: {
      attributes: {
        class: "view-rich-editor__prosemirror",
        role: "textbox",
        "aria-label": "Rich message content",
        "aria-multiline": "true",
        spellcheck: "true",
      },
      transformPastedHTML: sanitizePastedHtml,
      handleKeyDown: (_view, event) => {
        if (!(event.ctrlKey || event.metaKey) || event.altKey || event.code !== "KeyK") return false;
        event.preventDefault();
        setOpenPanel("link");
        return true;
      },
    },
    onUpdate: ({ editor: current }) => {
      const next = documentFromTiptapJson(current.getJSON(), documentRef.current);
      documentRef.current = next;
      onDocumentChangeRef.current(next);
    },
  });

  useEffect(() => {
    if (!editor) return;
    const expected = documentToTiptapJson(document);
    if (JSON.stringify(editor.getJSON()) !== JSON.stringify(expected)) {
      editor.commands.setContent(expected, { emitUpdate: false });
    }
  }, [document, editor]);

  const localDiagnostics = useMemo(() => validateBotContentDocument(document), [document]);
  const diagnostics = [
    ...localDiagnostics,
    ...(compileResult?.errors ?? []),
    ...(compileResult?.warnings ?? []),
  ];
  const togglePanel = (panel: Exclude<OpenPanel, null>) => setOpenPanel((current) => current === panel ? null : panel);

  return (
    <CustomEmojiStateProvider adapter={customEmojiAdapter}>
      <section className="view-text-editor" aria-label="Rich text editor" aria-busy={saveState === "saving" || undefined}>
      <div className="view-rich-editor__toolbar-shell">
        {editor ? (
          <RichTextToolbar
            editor={editor}
            variablePickerOpen={openPanel === "variables"}
            emojiPickerOpen={openPanel === "emoji"}
            linkEditorOpen={openPanel === "link"}
            onToggleVariablePicker={() => togglePanel("variables")}
            onToggleEmojiPicker={() => togglePanel("emoji")}
            onToggleLinkEditor={() => togglePanel("link")}
          />
        ) : <div className="view-rich-toolbar view-rich-toolbar--loading" aria-label="Loading editor" />}
        {editor ? <>
          <VariablePickerPopover editor={editor} open={openPanel === "variables"} onClose={() => setOpenPanel(null)} />
          <EmojiPickerPopover editor={editor} open={openPanel === "emoji"} onClose={() => setOpenPanel(null)} adapter={customEmojiAdapter} />
          <LinkEditorPopover editor={editor} open={openPanel === "link"} onClose={() => setOpenPanel(null)} />
        </> : null}
      </div>

      <div className="view-rich-editor__workspace">
        <section className="view-rich-editor__canvas" aria-label="Message document">
          <div className="view-rich-editor__canvas-heading">
            <span>Message</span>
            <small>Use $ in the compact editor or the variable button here.</small>
          </div>
          {editor ? <>
            <EditorContent editor={editor} />
            <SlashCommandMenu
              editor={editor}
              onOpenVariablePicker={() => setOpenPanel("variables")}
              onOpenEmojiPicker={() => setOpenPanel("emoji")}
            />
          </> : <div className="view-rich-editor__loading">Preparing editor…</div>}
        </section>
        <TelegramCompiledPreview result={compileResult} values={previewValues} onValuesChange={onPreviewValuesChange} onSendPreview={onSendPreview} />
      </div>

      <footer className="view-rich-editor__statusbar">
        <div className="view-rich-editor__diagnostic-summary">
          {diagnostics.length === 0 ? <><CircleCheck aria-hidden="true" /><span>No content issues</span></> : <><CircleAlert aria-hidden="true" /><span>{diagnostics.length} {diagnostics.length === 1 ? "issue" : "issues"}</span></>}
          {diagnostics.length > 0 ? (
            <details>
              <summary>View diagnostics</summary>
              <div>
                {diagnostics.map((diagnostic, index) => <p className={`is-${diagnostic.severity}`} key={`${diagnostic.code}-${index}`}><strong>{diagnostic.severity}</strong><span>{diagnostic.message}</span></p>)}
              </div>
            </details>
          ) : null}
        </div>
        <SaveState state={saveState} onRetry={onSaveRetry} />
      </footer>
      </section>
    </CustomEmojiStateProvider>
  );
}

function SaveState({ state, onRetry }: { state: RichEditorSaveState; onRetry?(): void }) {
  const label = state === "saving" ? "Saving…"
    : state === "saved" ? "Saved"
      : state === "dirty" ? "Waiting to save"
        : state === "error" ? "Save failed"
          : "Ready";
  return (
    <div className={`view-rich-editor__save-state is-${state}`} role="status" aria-live="polite">
      {state === "saving" ? <LoaderCircle aria-hidden="true" /> : state === "error" ? <CircleAlert aria-hidden="true" /> : <CircleCheck aria-hidden="true" />}
      <span>{label}</span>
      {state === "error" && onRetry ? <button type="button" onClick={onRetry}>Retry</button> : null}
    </div>
  );
}

export type {
  BotContentBlock,
  BotContentDocument,
  BotContentInlineNode,
  BotContentMark,
  CompileDiagnostic,
  CompiledTelegramMessage,
  ExistingVariableReference,
  TelegramCompileResult,
  TelegramMessageEntity,
} from "./model";
export { documentFromLegacyTemplate, legacyTemplateFromDocument } from "./legacy-adapter";
export { documentFromTiptapJson, documentToTiptapJson } from "./conversion";
