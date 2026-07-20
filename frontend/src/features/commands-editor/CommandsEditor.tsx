import type { ActionOptions, ActionSpec, CommandsSpec, HandlerCreateOptions, HandlerUsage } from "../../domain/project";
import { actionFor } from "../../domain/project";
import { ActionEditor, type HandlerActions } from "../action-editor/ActionEditor";

export function CommandsEditor({
  value,
  sourcePath,
  revision,
  options,
  handlerActions,
  onChange,
}: {
  value: CommandsSpec;
  sourcePath: string;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onChange(value: CommandsSpec): void;
}) {
  return (
    <section className="editor editor--wide" aria-label="Commands editor">
      <header className="editor__header"><div><p className="eyebrow">Global routing</p><h2>Commands</h2><small>{sourcePath}</small></div></header>
      <div className="form-grid">
        {value.commands.map((command, index) => (
          <article className="resource-card" key={`${command.name}-${index}`}>
            <header><strong>/{command.name || "new_command"}</strong><button type="button" className="button--quiet" onClick={() => onChange({ ...value, commands: value.commands.filter((_, current) => current !== index) })}>Remove</button></header>
            <label>Command name<input value={command.name} onChange={(event) => onChange({ ...value, commands: value.commands.map((item, current) => current === index ? { ...item, name: event.target.value.replace(/^\//, "") } : item) })} /></label>
            <label>Description<input value={command.description ?? ""} onChange={(event) => onChange({ ...value, commands: value.commands.map((item, current) => current === index ? { ...item, description: event.target.value || undefined } : item) })} /></label>
            <ActionEditor action={command.action} onChange={(action) => onChange({ ...value, commands: value.commands.map((item, current) => current === index ? { ...item, action } : item) })} options={options} scope={{ expectedKind: "command" }} handlerActions={handlerActions} createOptions={{ attachment: { type: "command", command: command.name }, target_revision: revision }} />
          </article>
        ))}
        <button type="button" className="button--quiet" onClick={() => onChange({ ...value, commands: [...value.commands, { name: nextCommand(value), action: actionFor("noop") }] })}>Add command</button>
        <FallbackEditor title="Message fallback" action={value.message_fallback} kind="message" options={options} handlerActions={handlerActions} createOptions={{ attachment: { type: "global_message_fallback" }, target_revision: revision }} onChange={(message_fallback) => onChange({ ...value, message_fallback })} />
        <FallbackEditor title="Unknown command fallback" action={value.command_fallback} kind="command" options={options} handlerActions={handlerActions} createOptions={{ attachment: { type: "global_command_fallback" }, target_revision: revision }} onChange={(command_fallback) => onChange({ ...value, command_fallback })} />
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
        ? <><ActionEditor action={action} onChange={onChange} options={options} scope={{ expectedKind: kind }} handlerActions={handlerActions} createOptions={createOptions} /><button type="button" className="button--quiet" onClick={() => onChange(undefined)}>Disable fallback</button></>
        : <button type="button" className="button--quiet" onClick={() => onChange(actionFor("noop"))}>Enable fallback</button>}
    </fieldset>
  );
}

function nextCommand(value: CommandsSpec): string {
  let number = value.commands.length + 1;
  while (value.commands.some((command) => command.name === `command_${number}`)) number += 1;
  return `command_${number}`;
}

export type { HandlerActions, HandlerUsage };
