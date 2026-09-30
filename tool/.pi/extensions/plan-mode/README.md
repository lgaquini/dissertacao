# Plan Mode Extension — Dual-Model Workflow

A pi extension that implements a **dual-model planning workflow**:

- **Planning phase**: Use a stronger, more capable (and typically more expensive) model to analyze, explore, and create a detailed implementation plan.
- **Execution phase**: Use a cheaper, weaker (but faster) model to implement the plan step by step.

This lets you allocate your best reasoning where it matters most — designing the approach — and save costs during mechanical implementation.

---

## Features

- **Automatic model switching**: The extension switches models for you when transitioning between planning and execution.
- **Read-only planning mode**: Disables write tools during planning so the planner only explores and analyzes.
- **Bash allowlist**: Only safe read-only bash commands are permitted during planning.
- **Plan extraction**: Automatically extracts numbered steps from `Plan:` sections in assistant responses.
- **Progress tracking**: Widget shows completion status during execution.
- **`[DONE:n]` markers**: The execution model marks steps complete as it goes.
- **Session persistence**: Your model preferences, plan state, and progress survive session resume.

---

## Commands

| Command | Description |
|---------|-------------|
| `/plan` | Toggle plan mode on/off |
| `/plan-model <provider/id>` | Set the model used for **planning** (e.g. `anthropic/claude-opus-4`) |
| `/exec-model <provider/id>` | Set the model used for **execution** (e.g. `openai/gpt-4.1-mini`) |
| `/todos` | Show current plan progress |
| `Ctrl+Alt+P` | Toggle plan mode (keyboard shortcut) |

---

## Setup

1. **Install the extension** by placing this directory in your project-local `.pi/extensions/` folder.
2. **Set your models** using the commands above, or rely on the current active model.
3. **Toggle plan mode** with `/plan` or `Ctrl+Alt+P`.

### Example Configuration

```
/plan-model anthropic/claude-opus-4
/exec-model openai/gpt-4.1-mini
/plan
```

This configures:
- **Claude Opus 4** for deep planning and analysis
- **GPT-4.1 Mini** for efficient plan execution

---

## How It Works

### Phase 1: Planning (Read-Only)

When you enable plan mode:

1. **Model switch**: If a planning model is configured, the extension automatically switches to it.
2. **Tool restrictions**: `edit` and `write` tools are disabled. Bash is filtered through an allowlist of read-only commands.
3. **Context injection**: The planner receives a system prompt instructing it to explore thoroughly and produce a detailed numbered plan.
4. **Exploration**: The model reads files, searches code, and asks clarifying questions without making changes.

The planner outputs a plan like:

```
Plan:
1. Read src/auth.ts to understand current auth flow
2. Add password validation function in src/validators.ts
3. Update login route in src/routes.ts to use the new validator
4. Add tests in tests/auth.test.ts
```

### Phase 2: Execution

When the plan is ready, choose **"Execute the plan"** from the prompt:

1. **Model switch**: The extension switches to your configured execution model (or restores the original model if none is set).
2. **Tool access restored**: Full tool access is re-enabled so the model can edit files.
3. **Context injection**: The execution model receives the plan steps and instructions to work through them in order.
4. **Progress tracking**: As the model completes steps, it includes `[DONE:1]`, `[DONE:2]`, etc. The widget updates automatically.

When all steps are complete, the extension shows a success message and restores your original model.

---

## Model Resolution

Models are specified as `provider/modelId`. The extension resolves them by:

1. Looking up via `ctx.modelRegistry.find(provider, modelId)`
2. Falling back to matching against the full available catalog

If a configured model is not found, the extension logs a warning and continues with the current model.

---

## Bash Allowlist (Planning Phase)

### Allowed commands
File inspection, search, directory listing, git read operations, package info queries, and system info.

### Blocked commands
File modification (`rm`, `mv`, `cp`, `mkdir`, ...), git writes (`git add`, `git commit`, ...), package installation, `sudo`, editors, and anything that redirects output to files.

---

## Session Persistence

The extension stores state in custom session entries, so:
- Model preferences survive across sessions
- Plan progress is restored on resume
- If the session is resumed mid-execution, `[DONE:n]` markers are re-scanned to reconstruct completion state

---

## Tips

- **Use a reasoning model for planning**: Models like `claude-opus-4` or `o3-mini` excel at analyzing complex codebases and designing robust plans.
- **Use a fast model for execution**: Models like `gpt-4.1-mini`, `claude-sonnet-4-5`, or local models work well for straightforward implementation.
- **Refine before executing**: If the plan isn't quite right, choose "Refine the plan" to iterate without leaving plan mode.
- **Run `/todos` anytime**: Check progress without waiting for the widget to update.
