import type {
  ActionOptions,
  ActionSpec,
  CommandSpec,
  CommandsSpec,
  HandlerCreateOptions,
} from "../../domain/project";
import { actionFor } from "../../domain/project";
import { ActionEditor, type HandlerActions } from "../action-editor/ActionEditor";

export function CommandEditor({
  value,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: CommandSpec;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: CommandSpec): void;
}) {
  return (
    <section className="editor" aria-label="Command editor">
      <div className="form-grid form-grid--command-settings">
        <label className="editor-field command-settings__name">
          <span>Name:</span>
          <span className="command-name-control">
            <span aria-hidden="true">/</span>
            <input
              aria-label="Command name"
              value={value.name}
              spellCheck={false}
              onChange={(event) => onChange({
                ...value,
                name: event.target.value.replace(/^\//, "").toLowerCase(),
              })}
            />
          </span>
        </label>
        <div className="editor-field command-settings__action">
          <span>Action:</span>
          <ActionEditor
            action={value.action}
            hideActionLabel
            onChange={(action) => onChange({ ...value, action })}
            options={options}
            scope={{ expectedKind: "command" }}
            handlerActions={handlerActions}
            createOptions={{
              attachment: { type: "command", command: value.name },
              target_revision: revision,
            }}
          />
        </div>
      </div>
    </section>
  );
}

export function CommandFallbacksEditor({
  value,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: CommandsSpec;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: CommandsSpec): void;
}) {
  return (
    <section className="editor editor--wide" aria-label="Command fallbacks editor">
      <div className="form-grid">
        <FallbackEditor
          title="Message fallback"
          action={value.message_fallback}
          kind="message"
          options={options}
          handlerActions={handlerActions}
          createOptions={{ attachment: { type: "global_message_fallback" }, target_revision: revision }}
          onChange={(message_fallback) => onChange({ ...value, message_fallback })}
        />
        <FallbackEditor
          title="Unknown command fallback"
          action={value.command_fallback}
          kind="command"
          options={options}
          handlerActions={handlerActions}
          createOptions={{ attachment: { type: "global_command_fallback" }, target_revision: revision }}
          onChange={(command_fallback) => onChange({ ...value, command_fallback })}
        />
      </div>
    </section>
  );
}

function FallbackEditor({
  title,
  action,
  kind,
  options,
  handlerActions,
  createOptions,
  onChange,
}: {
  title: string;
  action?: ActionSpec;
  kind: "message" | "command";
  options: ActionOptions;
  handlerActions: HandlerActions;
  createOptions?: HandlerCreateOptions;
  onChange(action?: ActionSpec): void;
}) {
  return (
    <fieldset>
      <legend>{title}</legend>
      {action
        ? <>
            <ActionEditor action={action} onChange={onChange} options={options} scope={{ expectedKind: kind }} handlerActions={handlerActions} createOptions={createOptions} />
            <button type="button" className="button--quiet" onClick={() => onChange(undefined)}>Disable fallback</button>
          </>
        : <button type="button" className="button--quiet" onClick={() => onChange(actionFor("noop"))}>Enable fallback</button>}
    </fieldset>
  );
}
