import { useState } from "react";

import type {
  ActionOptions,
  ActionSpec,
  CommandSpec,
  CommandsSpec,
  HandlerCreateOptions,
  Selection,
} from "../../domain/project";
import { actionFor } from "../../domain/project";
import { ActionEditor, type HandlerActions } from "../action-editor/ActionEditor";
import { AccessSelect, type AccessLevel } from "../../shared/ui/AccessSelect";
import { FormControlGroup, FormField, FormGrid } from "../../shared/ui/Form";

export function CommandEditor({
  value,
  revision,
  options,
  handlerActions,
  onOpenResource,
  onChange,
}: {
  value: CommandSpec;
  revision: string;
  options: ActionOptions;
  handlerActions: HandlerActions;
  onOpenResource?(selection: Selection): void;
  onChange(value: CommandSpec): void;
}) {
  const [accessMockup, setAccessMockup] = useState<AccessLevel>("everyone");
  return (
    <section className="editor" aria-label="Command editor">
      <FormGrid columns={2} className="command-settings">
        <FormField label="Name:">
          {(controlProps) => (
            <FormControlGroup prefix={<span aria-hidden="true">/</span>}>
            <input
              {...controlProps}
              aria-label="Command name"
              value={value.name}
              spellCheck={false}
              onChange={(event) => onChange({
                ...value,
                name: event.target.value.replace(/^\//, "").toLowerCase(),
              })}
            />
            </FormControlGroup>
          )}
        </FormField>
        <FormField label="Access:">
          {(controlProps) => <AccessSelect {...controlProps} ariaLabel="Command access" value={accessMockup} onChange={setAccessMockup} />}
        </FormField>
        <FormField label="Description:" span="full">
          {(controlProps) => (
            <input
              {...controlProps}
              value={value.description ?? ""}
              placeholder="Describe what this command does"
              onChange={(event) => onChange({
                ...value,
                description: event.target.value || undefined,
              })}
            />
          )}
        </FormField>
        <ActionEditor
          action={value.action}
          bare
          fieldLayout="row"
          compoundPrimary
          onOpenResource={onOpenResource}
          onChange={(action) => onChange({ ...value, action })}
          options={options}
          scope={{ expectedKind: "command" }}
          handlerActions={handlerActions}
          createOptions={{
            attachment: { type: "command", command: value.name },
            target_revision: revision,
          }}
        />
      </FormGrid>
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
      <FormGrid>
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
      </FormGrid>
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
