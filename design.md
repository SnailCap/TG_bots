# Telegram Bot Studio — Design Language

## Compact Graphite IDE Minimalism

Telegram Bot Studio uses **Compact Graphite IDE Minimalism**: a dark, desktop-first workspace with quiet graphite surfaces, thin separators, restrained typography, and a desaturated blue accent. The interface should feel like a modern IDE, not a dashboard or a game UI.

## Product context

- Audience: developers configuring autonomous Telegram bots.
- Primary job: navigate a project graph, edit resources, validate changes, and open custom Python code without visual distraction.
- Visual metaphor: a focused developer tool with a precise illuminated control surface.

## Core principles

1. **Graphite surfaces carry structure.** Use close neutral greys and 1 px borders before introducing shadows.
2. **Accent communicates interaction.** Desaturated blue is reserved for focus, selection, and available primary actions. Avoid persistent glow.
3. **One clear action at a time.** Primary actions are blue; destructive actions remain red; success remains green.
4. **Dense but breathable.** Use a compact 4/8 px spacing rhythm and a 14 px base type size. Keep the two-pane workspace full-height and independently scrollable.
5. **Desktop-native behaviour.** The title bar is compact and draggable; controls maintain clear focus and hover states.

## Tokens

| Role | Token | Value |
| --- | --- | --- |
| Workspace background | `--bg` | `#202226` |
| Primary surface | `--surface` | `#272a30` |
| Inset surface | `--surface-inset` | `#1c1f24` |
| Border | `--border` | `#3b3f47` |
| Primary blue | `--primary` | `#5e89be` |
| Bright blue | `--neon-bright` | `#93b6df` |
| Soft glow | `--neon-glow` | `rgb(94 137 190 / 14%)` |
| Strong glow | `--neon-glow-strong` | `rgb(94 137 190 / 22%)` |
| Success | `--success` | `#4fbe8a` |
| Warning | `--warning` | `#edb854` |
| Danger | `--danger` | `#f17e87` |

## Accent rules

- Prefer a border or subtle surface shift for hover and focus; do not use glow as the primary state indicator.
- Keep shadows low and local to menus only.
- Keep warning, error, and success states in their semantic colours rather than turning them blue.

## Components

- **Primary button:** muted blue fill; no decorative shadow.
- **Secondary button:** quiet graphite surface with a restrained hover border.
- **Resource settings forms:** follow the PyCharm desktop pattern on wide layouts: compact, light-weight label in a fixed left column; a 30 px high rectangular control in the right column; 2 px corners; graphite fill; and a thin muted-blue focus border. Keep complex cards and multiline code editors vertically structured.
- **Editor action strip:** place resource actions in a full-width, sticky bottom bar of the central panel. Separate it with one thin top rule and keep actions aligned to the right; do not mix status copy into this strip.
- **Select controls:** use the shared React `Select` component, not native `<select>`. It uses `--surface-raised`, a distinct `--border-strong` outline, and the shared SVG chevron. The chevron rotates 180 degrees in 160 ms while the menu opens with a short fade/scale entrance.
- **Context menus:** use the same elevated dropdown surface, a one-pixel blue-grey outline, compact 28 px rows, and a 140 ms fade/scale entrance.
- **Explorer resource icons:** use small semantic outline SVGs. `home`, `index`, and `start` views use a home glyph; other resources use their type glyph. Do not use generic rectangles as file icons.
- **Resource explorer:** collapsed categories by default. Open categories render their resources as a tree: a subtle vertical guide denotes category ownership and short branches lead to each nested item. The first child is a square create node styled like the global create control. An active resource receives a blue edge and restrained glow.
- **Dropdowns:** dark elevated surface, blue outline, and a short `160–200 ms` fade/scale entrance.
- **Action editor:** uses a blue left rail with a faint ambient glow to mark declarative behaviour.
- **Scrollbars:** thin, dark, and consistent with the interface; the thumb brightens only while used.

## Type, shape, and motion

- Font stack: Inter first, then system sans-serif fallbacks. Use 14 px base text with light-to-medium weights; monospace is only for code and raw JSON.
- Corners: 4 px for controls, 6 px for cards, 8 px for large welcome cards.
- Motion: `140–220 ms`, ease-out for entering and easing for state transitions. Motion must clarify a change, never decorate idle content.
- Honour `prefers-reduced-motion`; the global stylesheet removes nonessential animation.

## Accessibility guardrails

- Keyboard focus uses the bright blue outline plus glow.
- Maintain text contrast independently of neon effects.
- Buttons and category toggles use native controls with labels and `aria-expanded` where relevant.
- Do not encode state using colour alone; pair colour with text, border, icon, or selection state.

## Implementation

The source of truth for UI tokens and component states is [frontend/src/app/styles.css](frontend/src/app/styles.css). Extend existing semantic tokens rather than adding component-local colours.
