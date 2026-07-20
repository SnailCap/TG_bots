import type { ActionOptions, ButtonSpec, ViewSpec } from "../../domain/project";
import { actionFor } from "../../domain/project";
import { ActionEditor, type HandlerActions } from "../action-editor/ActionEditor";

export function ViewEditor({
  value,
  sourcePath,
  isNew,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: ViewSpec;
  sourcePath: string;
  isNew: boolean;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: ViewSpec): void;
}) {
  const useTemplate = "template" in value.text;
  const textSource = useTemplate ? value.text.template ?? "" : value.text.inline ?? "";
  const textSourceEmpty = textSource.trim().length === 0;
  const updateButton = (rowIndex: number, buttonIndex: number, button: ButtonSpec) => {
    onChange({
      ...value,
      keyboard: value.keyboard.map((row, currentRow) => currentRow === rowIndex
        ? row.map((item, currentButton) => currentButton === buttonIndex ? button : item)
        : row),
    });
  };
  const existingIds = value.keyboard.flat().map((button) => button.id);
  return (
    <section className="editor" aria-label="View editor">
      <header className="editor__header">
        <div>
          <p className="eyebrow">Schema v3 view</p>
          <h2>{isNew ? "New view" : value.id}</h2>
          <small>{sourcePath || "views/<id>.json"}</small>
        </div>
      </header>
      <div className="form-grid">
        <label>
          View ID
          <input disabled={!isNew} value={value.id} onChange={(event) => onChange({ ...value, id: event.target.value })} />
        </label>
        <label>
          Text source
          <select
            value={useTemplate ? "template" : "inline"}
            onChange={(event) => onChange({ ...value, text: event.target.value === "template" ? { template: "home.txt" } : { inline: "" } })}
          >
            <option value="inline">Inline text</option>
            <option value="template">Template file</option>
          </select>
        </label>
        <label>
          {useTemplate ? "Template path" : "Inline text"}
          <textarea
            aria-label={useTemplate ? "Template path" : "Inline text"}
            value={useTemplate ? value.text.template : value.text.inline}
            onChange={(event) => onChange({ ...value, text: useTemplate ? { template: event.target.value } : { inline: event.target.value } })}
          />
          {textSourceEmpty && <small className="error">{useTemplate ? "Template path is required." : "Inline text cannot be empty."}</small>}
        </label>
        <fieldset className="keyboard-editor">
          <legend>Inline keyboard</legend>
          {value.keyboard.map((row, rowIndex) => (
            <div className="keyboard-row" key={rowIndex}>
              {row.map((button, buttonIndex) => (
                <section className="button-card" key={button.id || buttonIndex}>
                  <header><strong>Button {rowIndex + 1}.{buttonIndex + 1}</strong></header>
                  <label>
                    Stable action ID
                    <input value={button.id} onChange={(event) => updateButton(rowIndex, buttonIndex, { ...button, id: event.target.value })} />
                  </label>
                  <label>
                    Text
                    <input value={button.text} onChange={(event) => updateButton(rowIndex, buttonIndex, { ...button, text: event.target.value })} />
                  </label>
                  <ActionEditor
                    action={button.action}
                    onChange={(action) => updateButton(rowIndex, buttonIndex, { ...button, action })}
                    options={options}
                    scope={{ expectedKind: "button" }}
                    handlerActions={handlerActions}
                    createOptions={isNew ? undefined : {
                      attachment: { type: "view_button", view_id: value.id, button_id: button.id },
                      target_revision: revision,
                    }}
                  />
                  <button type="button" className="button--quiet" onClick={() => onChange({
                    ...value,
                    keyboard: value.keyboard.map((item, current) => current === rowIndex ? item.filter((_, index) => index !== buttonIndex) : item),
                  })}>Remove button</button>
                </section>
              ))}
              <div className="button-row">
                <button type="button" className="button--quiet" onClick={() => onChange({
                  ...value,
                  keyboard: value.keyboard.map((item, current) => current === rowIndex
                    ? [...item, { id: nextButtonId(value.id, existingIds), text: "Button", action: actionFor("noop") }]
                    : item),
                })}>Add button</button>
                <button type="button" className="button--quiet" onClick={() => onChange({ ...value, keyboard: value.keyboard.filter((_, index) => index !== rowIndex) })}>Remove row</button>
              </div>
            </div>
          ))}
          <button type="button" className="button--quiet" onClick={() => onChange({ ...value, keyboard: [...value.keyboard, []] })}>Add row</button>
        </fieldset>
      </div>
    </section>
  );
}

function nextButtonId(viewId: string, existing: string[]): string {
  const prefix = `${viewId || "view"}.action`;
  let suffix = 1;
  while (existing.includes(`${prefix}_${suffix}`)) suffix += 1;
  return `${prefix}_${suffix}`;
}
