# Tutorial: create your first bot

This tutorial builds a small two-branch Telegram bot entirely in Studio. It
greets the user, either records a short request or shows an About message, and
demonstrates persisted input state.

## Prerequisites

- Telegram Bot Studio is running; for a source checkout, follow
  [development.md](development.md).
- You have created a bot with Telegram's `@BotFather` and copied its Bot API
  token.
- You have an empty directory dedicated to this project. One directory is one
  bot; do not select the repository root or a folder with unrelated files.

## 1. Create the project

1. Select **New** in the top bar.
2. Enter `Support Demo` as the project name.
3. Choose the empty project directory and select **Create**.

Studio creates `bot.json`, `flows/`, `scripts/`, `assets/` and the local runtime
directory. The token will not be written into any of those portable files.

## 2. Create the flow

In Project Explorer select **+ Flow**, name it `Main`, then double-click the new
flow. Build this graph:

```text
Start -> Greeting -> Choice
                      ├─ New request -> Ask description -> Confirmation -> End
                      │                    └─ error -> Invalid input -> End
                      └─ About       -> About message  -> End
```

Use the node toolbar above the graph to add nodes, drag them into place, then
drag from a source handle to the next node. Select a node to edit it in the
Inspector.

Configure the nodes as follows:

1. **Start**: no properties are required.
2. **Send Message** (`Greeting`): `Hello! What would you like to do?`
3. **Choice**:
   - message: `Choose an option`;
   - keyboard: `inline`;
   - choices, one per line: `New request | new_request` and
     `About | about`.
4. **Ask Input** (`Ask description`):
   - question: `Describe your request in one message.`;
   - variable: `request.description`;
   - type: `string`;
   - required: enabled;
   - validation regex: `.{3,}`;
   - validation error message: `Please enter at least three characters.`;
   - maximum attempts: `3`.
5. **Send Message** (`Confirmation`):
   `Thanks. I saved: {{ request.description }}`.
6. **Send Message** (`About message`):
   `This bot was assembled in Telegram Bot Studio.`
7. **Send Message** (`Invalid input`):
   `Too many invalid replies. Send /start to try again.`
8. Add an **End** node to each branch.

Connect the two Choice option handles to their corresponding branches. Connect
Ask Input's `success` handle to Confirmation and its `error` handle to Invalid
input. Connect all other ordinary nodes through their default/success handle.
The graph must have exactly one Start entry and every non-End branch must lead
somewhere.

Press **Ctrl+S** (or the editor Save button). A dot in the tab title means the
flow still has unsaved changes.

## 3. Configure the bot

Double-click **Bot Settings** in Project Explorer.

1. Paste the Bot API token and select **Save securely**. Studio validates it
   through Telegram and shows the bot ID and username.
2. Select `Main` as **Start flow**.
3. Choose **Reset current flow** for `/start` behavior.
4. Select **Save settings**.

The token is stored by the operating-system keyring. `bot.json` contains only a
secret reference and the public bot identity, so the project definition can be
committed without exposing the token.

## 4. Validate and run

Select **Validate** in the top bar. Resolve every error shown in Console; common
causes are a missing start flow, an unconnected node or an ambiguous branch.
Warnings may describe a repairable but non-blocking issue.

Select **Run**. The status should progress from `starting` to `running` and show
the connected bot username. Open the bot in Telegram and send `/start`.

Check both paths:

- select **About** and confirm that the About message is followed by completion;
- send `/start` again, select **New request**, enter text, and confirm that the
  template contains exactly that saved answer.

Execution events, transitions and errors appear in the bottom Console. They are
also persisted in `.botstudio/runtime.db`.

## 5. Verify resume after restart

1. Send `/start`, choose **New request**, and wait at the description question.
2. Select **Stop** in Studio.
3. Start the bot again, then send the description without another `/start`.

The reply is accepted because the pending Ask Input node was committed to
SQLite before the bot waited. A full backend restart has the same persistence
property. Sending `/start` instead would reset this conversation because this
tutorial selected the `reset` policy.

## Troubleshooting

- **Token validation fails:** verify that the token is complete, the machine can
  reach Telegram, and the OS credential/keyring service is available.
- **Run stays in error:** open Console, select the referenced validation issue,
  save the repaired flow, then Validate again.
- **Buttons do nothing:** make sure each Choice option handle has exactly one
  outgoing button transition.
- **Template error:** `{{ request.description }}` exists only after Ask Input;
  do not route the About branch through the Confirmation node.
- **No response to ordinary text:** a completed or missing session must be
  started with `/start`.
