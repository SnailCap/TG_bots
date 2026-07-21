# UX audit — Telegram Bot Studio

Audit date: 2026-07-20

The Studio is a desktop-first editor for the declarative schema v3 project graph. The audit covers the project entry screen, resource explorer, editor workspace, validation sidebar, preview and custom-handler workflow.

## Priority findings

| Priority | Area | Problem | User impact | Resolution in this refactor |
| --- | --- | --- | --- | --- |
| Critical | Workspace header and editor footer | The selected project, selected resource and unsaved state were split across a compact header and a small footer note. | It was easy to lose context or leave an editor without noticing that its draft had not been written to disk. | The header now identifies the project and save state; each editor has a context bar and a persistent save bar with an explicit outcome. Navigation still asks before discarding a draft. |
| Critical | Resource deletion | Delete actions used the same footer area as Save and gave no explanation before the native confirmation. | Accidental removal was visually too close to the primary action. | Destructive actions are visually separated, labelled as resource/binding deletion and explain the consequence before confirmation. |
| High | Empty and validation states | The preview, no-selection workspace and clean-validation states were plain muted sentences. | Users could not distinguish “nothing selected yet” from missing data or a successful validation result. | Dedicated empty, no-selection and success states now state the next useful action and the meaning of a clean graph. |
| High | Project entry | Opening and creating projects were visually equivalent groups of fields with terse helper text. | The choice between continuing work and creating a deployable starter was not clear. | The entry screen separates the two tasks, explains their outcomes and makes folder requirements explicit. |
| High | Navigation | The explorer showed an active row but did not expose its state to assistive technology; project identity was easy to overlook. | Keyboard and screen-reader users had weaker orientation, and long paths hid useful context. | Active resources use `aria-current`; project identity and paths have clear, compact hierarchy and full-path tooltips. |
| Medium | System feedback | Backend health used colour-heavy pills, while busy work only changed the cursor. | A status could be missed, particularly during slow network/file operations. | Backend health has a semantic status and indicator; workspace activity has a textual live status and reduced-motion-safe indicator. |
| Medium | Visual consistency | Controls, cards, panels, diagnostics and action groups used locally defined colours and spacing. | Long editing sessions felt visually noisy and made action priority inconsistent. | Shared tokens now govern surfaces, text, borders, semantic status colours, radii, focus, spacing and component states. |
| Medium | Responsive layout | The document enforced an 800px minimum width and the three-column workspace had only one partial breakpoint. | Small windows created horizontal overflow and hid useful information. | Layout collapses the inspector below the editor, then stacks the explorer and content on narrow screens. |
| Medium | Accessibility | Focus rings were browser-dependent and some success/error feedback lacked live semantics. | Keyboard navigation and non-colour interpretation were unreliable. | A visible focus style, `role=status`/`role=alert`, text labels and reduced-motion support are applied consistently. |

## Refactoring plan and status

1. **Critical UX problems — complete:** durable save visibility, safer destructive actions, explicit editor context.
2. **Structure and navigation — complete:** clearer project entry, contextual workspace header and selected-resource treatment.
3. **UI consistency — complete for shared primitives:** tokens and variants cover buttons, form controls, panels, cards, status badges, diagnostics, empty states and loading feedback. Existing feature components reuse these primitives without a parallel UI library.
4. **Visual refinement — complete:** compact technical desktop visual language; no decorative gradients or glass effects.
5. **Accessibility — complete for changed surfaces:** focus visibility, semantic status feedback, non-colour labels, responsive behaviour and reduced motion.
6. **React maintenance — complete for changed flow:** no new derived state was introduced; editor context is computed from existing editor state and async states remain local to their operations.

## Follow-up candidates

- Replace native confirmation/alert dialogs with a shared accessible dialog once a non-destructive cancel/retry pattern is designed across all operations.
- Add search/filtering and counts to the explorer for large projects.
- Add component-level skeletons only where API latency measurements demonstrate that they improve perceived performance.
- Add end-to-end coverage for a real created fixture and explicit API-failure injection.
