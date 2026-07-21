import { TemplateComposer } from "../template-composer/TemplateComposer";

export function TemplateEditor({
  path,
  content,
  onContentChange,
}: {
  path: string;
  content: string;
  onContentChange(content: string): void;
}) {
  return (
    <section className="editor editor--template" aria-label="Template editor">
      <TemplateComposer path={path} content={content} onContentChange={onContentChange} />
    </section>
  );
}
