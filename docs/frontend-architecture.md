# Frontend architecture

The desktop client is Electron + React + TypeScript. Vite builds the renderer and
the Electron main/preload entries. The renderer contains presentation and editor
state only; all project and runtime mutations go through `/api/v1`.

## Process responsibilities

### Electron main

- starts one Python/FastAPI control-plane process in development and packaged
  builds;
- creates and owns the application window;
- provides native directory selection and reveal-in-folder operations;
- hides the backend child window on Windows and stops it on app quit;
- exposes no Node integration to the renderer.

### Preload

The context-isolated preload exposes a deliberately small `studioDesktop` API:
directory selection, path reveal, and backend connection information. Renderer
code cannot call arbitrary IPC or filesystem APIs.

### Renderer

```text
src/
├── app/                  providers and thin App composition
├── entities/             project/flow/runtime transport-facing models
├── features/
│   ├── flow-editor/      React Flow graph and node cards
│   ├── project/          project/workspace state
│   ├── runtime/          Run/Stop/status/SSE connection
│   ├── script-editor/    Monaco, actions and usages
│   └── settings/         bot token and start flow
├── widgets/
│   ├── top-bar/
│   ├── project-explorer/
│   ├── workspace/
│   ├── inspector/
│   ├── preview/
│   ├── console/
│   └── studio-shell/
└── shared/api/           HTTP client, tolerant decoders and DTOs
```

`App` only installs `StudioProvider` and composes `StudioShell`. CSS Modules stay
next to widgets/features; the small global stylesheet contains only reset/theme
tokens and root sizing.

## State ownership

- Server state is fetched and saved through `StudioApi`.
- Workspace state owns open tabs, the active tab and dirty flags.
- Each editor owns its working document until Save succeeds.
- Selection/navigation state connects graph, Inspector, validation, scripts and
  usages without placing flow execution rules in React.
- Runtime connection state combines HTTP status polling with SSE log events and
  exposes a small Run/Stop controller.

Redux is intentionally not used: there is no large cross-page client domain and
React context plus local reducers keep ownership explicit.

## Flow serialization

React Flow needs `nodes` and `edges` with renderer-specific handles. The portable
backend document uses domain `nodes` and `transitions`. `flowTransport.ts` is the
only translation boundary:

- load maps `config` to node data and transitions to edges;
- save maps renderer data back to schema-versioned `config` and transition
  fields;
- coordinates, IDs and branch outcomes are preserved;
- tolerant input normalization is limited to transport compatibility and never
  changes runtime semantics.

## Unsaved changes

Node movement, connections, Inspector edits and file edits mark the owning tab
dirty. Closing a dirty tab asks before discard. `Ctrl+S` saves the active editor.
The backend's atomic writes protect the last saved version; no optimistic local
write is treated as committed before the API responds.

## Error and event handling

API errors are normalized to a user-facing message plus status/code when
available. The shell shows immediate operation errors, while Console retains
structured validation and runtime events. Entity references navigate to a flow
node or script line. The SSE client reconnects using browser behavior; status is
also fetched over HTTP after a reconnect so events are not the sole state source.

## Security posture

Electron uses `contextIsolation`, disables `nodeIntegration`, and enables the
renderer sandbox. Token values are sent only to the local backend and are never
stored in frontend persistence or project JSON. Script content is edited as text
but executed only by the Python runtime boundary.
