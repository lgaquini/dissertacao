/**
 * Plan Mode Extension — Dual-Model Workflow
 *
 * Uses a stronger (more capable/expensive) model for read-only planning,
 * and a cheaper/weaker model for executing the plan.
 *
 * Commands:
 *   /plan              - Toggle plan mode
 *   /plan-model <id>   - Set planning model (e.g. anthropic/claude-opus-4)
 *   /exec-model <id>   - Set execution model (e.g. openai/gpt-4.1-mini)
 *   /todos             - Show plan progress
 *   Ctrl+Alt+P         - Toggle plan mode
 */

import type { AgentMessage } from "@earendil-works/pi-agent-core";
import type { AssistantMessage, TextContent } from "@earendil-works/pi-ai";
import type { ExtensionAPI, ExtensionContext, Model } from "@earendil-works/pi-coding-agent";
import { Key } from "@earendil-works/pi-tui";

// ── Types ─────────────────────────────────────────────────────────────

interface TodoItem {
	step: number;
	text: string;
	completed: boolean;
}

interface PlanModeConfig {
	enabled: boolean;
	executing: boolean;
	todos: TodoItem[];
	toolsBeforePlanMode?: string[];
	planningModelId?: string;
	executionModelId?: string;
	previousModelId?: string;
}

// ── Utils ─────────────────────────────────────────────────────────────

const DESTRUCTIVE_PATTERNS = [
	/\brm\b/i, /\brmdir\b/i, /\bmv\b/i, /\bcp\b/i, /\bmkdir\b/i, /\btouch\b/i,
	/\bchmod\b/i, /\bchown\b/i, /\bchgrp\b/i, /\bln\b/i, /\btee\b/i, /\btruncate\b/i,
	/\bdd\b/i, /\bshred\b/i, /(^|[^<])>(?!>)/, />>/,
	/\bnpm\s+(install|uninstall|update|ci|link|publish)/i,
	/\byarn\s+(add|remove|install|publish)/i,
	/\bpnpm\s+(add|remove|install|publish)/i,
	/\bpip\s+(install|uninstall)/i,
	/\bapt(-get)?\s+(install|remove|purge|update|upgrade)/i,
	/\bbrew\s+(install|uninstall|upgrade)/i,
	/\bgit\s+(add|commit|push|pull|merge|rebase|reset|checkout|branch\s+-[dD]|stash|cherry-pick|revert|tag|init|clone)/i,
	/\bsudo\b/i, /\bsu\b/i, /\bkill\b/i, /\bpkill\b/i, /\bkillall\b/i,
	/\breboot\b/i, /\bshutdown\b/i,
	/\bsystemctl\s+(start|stop|restart|enable|disable)/i,
	/\bservice\s+\S+\s+(start|stop|restart)/i,
	/\b(vim?|nano|emacs|code|subl)\b/i,
];

const SAFE_PATTERNS = [
	/^\s*cat\b/, /^\s*head\b/, /^\s*tail\b/, /^\s*less\b/, /^\s*more\b/,
	/^\s*grep\b/, /^\s*find\b/, /^\s*ls\b/, /^\s*pwd\b/, /^\s*echo\b/,
	/^\s*printf\b/, /^\s*wc\b/, /^\s*sort\b/, /^\s*uniq\b/, /^\s*diff\b/,
	/^\s*file\b/, /^\s*stat\b/, /^\s*du\b/, /^\s*df\b/, /^\s*tree\b/,
	/^\s*which\b/, /^\s*whereis\b/, /^\s*type\b/, /^\s*env\b/, /^\s*printenv\b/,
	/^\s*uname\b/, /^\s*whoami\b/, /^\s*id\b/, /^\s*date\b/, /^\s*cal\b/,
	/^\s*uptime\b/, /^\s*ps\b/, /^\s*top\b/, /^\s*htop\b/, /^\s*free\b/,
	/^\s*git\s+(status|log|diff|show|branch|remote|config\s+--get)/i,
	/^\s*git\s+ls-/i,
	/^\s*npm\s+(list|ls|view|info|search|outdated|audit)/i,
	/^\s*yarn\s+(list|info|why|audit)/i,
	/^\s*node\s+--version/i, /^\s*python\s+--version/i,
	/^\s*curl\s/i, /^\s*wget\s+-O\s*-/i, /^\s*jq\b/, /^\s*sed\s+-n/i,
	/^\s*awk\b/, /^\s*rg\b/, /^\s*fd\b/, /^\s*bat\b/, /^\s*eza\b/,
];

function isSafeCommand(command: string): boolean {
	const isDestructive = DESTRUCTIVE_PATTERNS.some((p) => p.test(command));
	const isSafe = SAFE_PATTERNS.some((p) => p.test(command));
	return !isDestructive && isSafe;
}

function cleanStepText(text: string): string {
	let cleaned = text
		.replace(/\*{1,2}([^*]+)\*{1,2}/g, "$1")
		.replace(/`([^`]+)`/g, "$1")
		.replace(
			/^(Use|Run|Execute|Create|Write|Read|Check|Verify|Update|Modify|Add|Remove|Delete|Install)\s+(the\s+)?/i,
			"",
		)
		.replace(/\s+/g, " ")
		.trim();
	if (cleaned.length > 0) cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
	if (cleaned.length > 50) cleaned = `${cleaned.slice(0, 47)}...`;
	return cleaned;
}

function extractTodoItems(message: string): TodoItem[] {
	const items: TodoItem[] = [];
	const headerMatch = message.match(/\*{0,2}Plan:\*{0,2}\s*\n/i);
	if (!headerMatch) return items;
	const planSection = message.slice(message.indexOf(headerMatch[0]) + headerMatch[0].length);
	const numberedPattern = /^\s*(\d+)[.)]\s+\*{0,2}([^*\n]+)/gm;
	for (const match of planSection.matchAll(numberedPattern)) {
		const text = match[2].trim().replace(/\*{1,2}$/, "").trim();
		if (text.length > 5 && !text.startsWith("`") && !text.startsWith("/") && !text.startsWith("-")) {
			const cleaned = cleanStepText(text);
			if (cleaned.length > 3) items.push({ step: items.length + 1, text: cleaned, completed: false });
		}
	}
	return items;
}

function extractDoneSteps(message: string): number[] {
	const steps: number[] = [];
	for (const match of message.matchAll(/\[DONE:(\d+)\]/gi)) {
		const step = Number(match[1]);
		if (Number.isFinite(step)) steps.push(step);
	}
	return steps;
}

function markCompletedSteps(text: string, items: TodoItem[]): number {
	const doneSteps = extractDoneSteps(text);
	for (const step of doneSteps) {
		const item = items.find((t) => t.step === step);
		if (item) item.completed = true;
	}
	return doneSteps.length;
}

function modelToId(model: Model | undefined): string | undefined {
	if (!model) return undefined;
	return `${model.provider}/${model.id}`;
}

function resolveModel(ctx: ExtensionContext, modelId: string): Model | undefined {
	const [provider, ...idParts] = modelId.split('/');
	const id = idParts.join('/');
	return ctx.modelRegistry.find(provider, id) ?? ctx.modelRegistry.getAvailable().find(m => `${m.provider}/${m.id}` === modelId);
}

// ── Extension ─────────────────────────────────────────────────────────

const PLAN_MODE_TOOLS = ["read", "bash", "grep", "find", "ls", "questionnaire"];
const NORMAL_MODE_TOOLS = ["read", "bash", "edit", "write"];
const PLAN_MODE_DISABLED_TOOLS = new Set<string>(["edit", "write"]);
const PLAN_MANAGED_TOOLS = new Set<string>([...PLAN_MODE_TOOLS, ...NORMAL_MODE_TOOLS]);

function isAssistantMessage(m: AgentMessage): m is AssistantMessage {
	return m.role === "assistant" && Array.isArray(m.content);
}

function getTextContent(message: AssistantMessage): string {
	return message.content.filter((block): block is TextContent => block.type === "text").map((block) => block.text).join("\n");
}

export default function planModeExtension(pi: ExtensionAPI): void {
	let planModeEnabled = false;
	let executionMode = false;
	let todoItems: TodoItem[] = [];
	let toolsBeforePlanMode: string[] | undefined;
	let planningModelId: string | undefined;
	let executionModelId: string | undefined;
	let previousModelId: string | undefined;

	function uniqueToolNames(toolNames: string[]): string[] {
		return [...new Set(toolNames)];
	}

	function getPlanModeTools(activeToolNames: string[]): string[] {
		return uniqueToolNames([...activeToolNames.filter((name) => !PLAN_MODE_DISABLED_TOOLS.has(name)), ...PLAN_MODE_TOOLS]);
	}

	function getNormalModeTools(activeToolNames: string[]): string[] {
		return uniqueToolNames([...NORMAL_MODE_TOOLS, ...activeToolNames.filter((name) => !PLAN_MANAGED_TOOLS.has(name))]);
	}

	function enablePlanModeTools(): void {
		if (toolsBeforePlanMode === undefined) toolsBeforePlanMode = pi.getActiveTools();
		pi.setActiveTools(getPlanModeTools(toolsBeforePlanMode));
	}

	function restoreNormalModeTools(): void {
		pi.setActiveTools(toolsBeforePlanMode ?? getNormalModeTools(pi.getActiveTools()));
		toolsBeforePlanMode = undefined;
	}

	async function switchToModel(ctx: ExtensionContext, modelId: string | undefined, label: string): Promise<boolean> {
		if (!modelId) return false;
		const model = resolveModel(ctx, modelId);
		if (!model) {
			ctx.ui.notify(`${label} model not found: ${modelId}`, "warning");
			return false;
		}
		const currentId = modelToId(ctx.model);
		if (currentId === modelId) return true; // already on this model
		const success = await pi.setModel(model);
		if (success) {
			ctx.ui.notify(`Switched to ${label} model: ${modelId}`, "info");
			return true;
		} else {
			ctx.ui.notify(`Failed to switch to ${label} model: ${modelId}`, "error");
			return false;
		}
	}

	async function restorePreviousModel(ctx: ExtensionContext): Promise<void> {
		if (!previousModelId) return;
		const model = resolveModel(ctx, previousModelId);
		if (model) {
			const success = await pi.setModel(model);
			if (success) ctx.ui.notify(`Restored original model: ${previousModelId}`, "info");
		}
		previousModelId = undefined;
	}

	function persistState(): void {
		pi.appendEntry("plan-mode", {
			enabled: planModeEnabled,
			executing: executionMode,
			todos: todoItems,
			toolsBeforePlanMode,
			planningModelId,
			executionModelId,
			previousModelId,
		});
	}

	function updateStatus(ctx: ExtensionContext): void {
		if (executionMode && todoItems.length > 0) {
			const completed = todoItems.filter((t) => t.completed).length;
			const execLabel = executionModelId ? ` [${executionModelId}]` : "";
			ctx.ui.setStatus("plan-mode", ctx.ui.theme.fg("accent", `📋 ${completed}/${todoItems.length}${execLabel}`));
		} else if (planModeEnabled) {
			const modelLabel = planningModelId ? ` (${planningModelId})` : "";
			ctx.ui.setStatus("plan-mode", ctx.ui.theme.fg("warning", `⏸ plan${modelLabel}`));
		} else {
			ctx.ui.setStatus("plan-mode", undefined);
		}

		if (executionMode && todoItems.length > 0) {
			const lines = todoItems.map((item) => {
				if (item.completed) return ctx.ui.theme.fg("success", "☑ ") + ctx.ui.theme.fg("muted", ctx.ui.theme.strikethrough(item.text));
				return `${ctx.ui.theme.fg("muted", "☐ ")}${item.text}`;
			});
			ctx.ui.setWidget("plan-todos", lines);
		} else if (planModeEnabled && planningModelId) {
			ctx.ui.setWidget("plan-model", [ctx.ui.theme.fg("dim", `Planning model: ${planningModelId}`)]);
		} else {
			ctx.ui.setWidget("plan-todos", undefined);
			ctx.ui.setWidget("plan-model", undefined);
		}
	}

	async function togglePlanMode(ctx: ExtensionContext): Promise<void> {
		planModeEnabled = !planModeEnabled;
		executionMode = false;

		if (planModeEnabled) {
			// Save current model before switching
			previousModelId = modelToId(ctx.model);
			enablePlanModeTools();
			ctx.ui.notify("Plan mode enabled. Write tools disabled.");
			// Switch to planning model if configured
			if (planningModelId) await switchToModel(ctx, planningModelId, "planning");
		} else {
			todoItems = [];
			restoreNormalModeTools();
			ctx.ui.notify("Plan mode disabled. Full access restored.");
			await restorePreviousModel(ctx);
		}
		updateStatus(ctx);
		persistState();
	}

	// ── Commands ──────────────────────────────────────────────────────

	pi.registerCommand("plan", {
		description: "Toggle plan mode (read-only exploration)",
		handler: async (_args, ctx) => togglePlanMode(ctx),
	});

	pi.registerCommand("plan-model", {
		description: "Set the model used for planning (e.g. /plan-model anthropic/claude-opus-4)",
		handler: async (args, ctx) => {
			const id = args.trim();
			if (!id) {
				ctx.ui.notify(`Current planning model: ${planningModelId ?? "(not set, uses current model)"}`, "info");
				return;
			}
			const model = resolveModel(ctx, id);
			if (!model) {
				ctx.ui.notify(`Model not found: ${id}`, "error");
				return;
			}
			planningModelId = `${model.provider}/${model.id}`;
			ctx.ui.notify(`Planning model set to: ${planningModelId}`, "info");
			persistState();
			updateStatus(ctx);
			// If already in plan mode, switch immediately
			if (planModeEnabled && !executionMode) await switchToModel(ctx, planningModelId, "planning");
		},
	});

	pi.registerCommand("exec-model", {
		description: "Set the model used for execution (e.g. /exec-model openai/gpt-4.1-mini)",
		handler: async (args, ctx) => {
			const id = args.trim();
			if (!id) {
				ctx.ui.notify(`Current execution model: ${executionModelId ?? "(not set, restores original model)"}`, "info");
				return;
			}
			const model = resolveModel(ctx, id);
			if (!model) {
				ctx.ui.notify(`Model not found: ${id}`, "error");
				return;
			}
			executionModelId = `${model.provider}/${model.id}`;
			ctx.ui.notify(`Execution model set to: ${executionModelId}`, "info");
			persistState();
			updateStatus(ctx);
			// If already executing, switch immediately
			if (executionMode) await switchToModel(ctx, executionModelId, "execution");
		},
	});

	pi.registerCommand("todos", {
		description: "Show current plan progress",
		handler: async (_args, ctx) => {
			if (todoItems.length === 0) {
				ctx.ui.notify("No todos. Create a plan first with /plan", "info");
				return;
			}
			const list = todoItems.map((item, i) => `${i + 1}. ${item.completed ? "✓" : "○"} ${item.text}`).join("\n");
			ctx.ui.notify(`Plan Progress:\n${list}`, "info");
		},
	});

	pi.registerShortcut(Key.ctrlAlt("p"), {
		description: "Toggle plan mode",
		handler: async (ctx) => togglePlanMode(ctx),
	});

	// ── Events ────────────────────────────────────────────────────────

	pi.registerFlag("plan", {
		description: "Start in plan mode (read-only exploration)",
		type: "boolean",
		default: false,
	});

	// Block destructive bash commands in plan mode
	pi.on("tool_call", async (event) => {
		if (!planModeEnabled || event.toolName !== "bash") return;
		const command = event.input.command as string;
		if (!isSafeCommand(command)) {
			return {
				block: true,
				reason: `Plan mode: command blocked (not allowlisted). Use /plan to disable plan mode first.\nCommand: ${command}`,
			};
		}
	});

	// Auto-switch model and inject phase-specific context before each turn
	pi.on("before_agent_start", async (_event, ctx) => {
		if (planModeEnabled && !executionMode) {
			// Planning phase: use planning model
			if (planningModelId) await switchToModel(ctx, planningModelId, "planning");
			return {
				message: {
					customType: "plan-mode-context",
					content: `[PLAN MODE ACTIVE — Planning Phase]
You are in PLAN MODE — a read-only exploration phase for safe code analysis.

Your role is to THINK DEEPLY and CREATE A DETAILED PLAN. Do not write any code yet.

Restrictions:
- Built-in edit and write tools are DISABLED
- Bash is restricted to read-only commands
- You cannot modify the filesystem

Your task:
1. Explore the codebase thoroughly using read, grep, find, ls, and safe bash commands
2. Ask clarifying questions if needed
3. Create a comprehensive, numbered plan under a "Plan:" header

Each step must be specific and actionable. Example:

Plan:
1. Read src/auth.ts to understand current auth flow
2. Add password validation function in src/validators.ts
3. Update login route in src/routes.ts to use the new validator
4. Add tests in tests/auth.test.ts

Do NOT attempt to make changes. Only plan.`,
					display: false,
				},
			};
		}

		if (executionMode && todoItems.length > 0) {
			// Execution phase: use execution model
			if (executionModelId) await switchToModel(ctx, executionModelId, "execution");
			const remaining = todoItems.filter((t) => !t.completed);
			const todoList = remaining.map((t) => `${t.step}. ${t.text}`).join("\n");
			return {
				message: {
					customType: "plan-execution-context",
					content: `[EXECUTING PLAN — Implementation Phase]
You are in EXECUTION MODE. Your job is to implement the plan efficiently.

Remaining steps:
${todoList}

Instructions:
- Execute each step in order
- After completing a step, include a [DONE:n] tag in your response
- Do not skip steps or add unplanned work
- If a step cannot be completed, explain why and continue to the next one`,
					display: false,
				},
			};
		}
	});

	// Filter out stale plan mode context when not in plan mode
	pi.on("context", async (event) => {
		if (planModeEnabled) return;
		return {
			messages: event.messages.filter((m) => {
				const msg = m as AgentMessage & { customType?: string };
				if (msg.customType === "plan-mode-context") return false;
				if (msg.role !== "user") return true;
				const content = msg.content;
				if (typeof content === "string") return !content.includes("[PLAN MODE ACTIVE]");
				if (Array.isArray(content)) {
					return !content.some((c) => c.type === "text" && (c as TextContent).text?.includes("[PLAN MODE ACTIVE]"));
				}
				return true;
			}),
		};
	});

	// Track progress after each turn
	pi.on("turn_end", async (event, ctx) => {
		if (!executionMode || todoItems.length === 0) return;
		if (!isAssistantMessage(event.message)) return;
		const text = getTextContent(event.message);
		if (markCompletedSteps(text, todoItems) > 0) updateStatus(ctx);
		persistState();
	});

	// Handle plan extraction and execution transition
	pi.on("agent_end", async (event, ctx) => {
		// Check if execution is complete
		if (executionMode && todoItems.length > 0) {
			if (todoItems.every((t) => t.completed)) {
				const completedList = todoItems.map((t) => `~~${t.text}~~`).join("\n");
				pi.sendMessage(
					{ customType: "plan-complete", content: `**Plan Complete!** ✓\n\n${completedList}`, display: true },
					{ triggerTurn: false },
				);
				executionMode = false;
				todoItems = [];
				updateStatus(ctx);
				await restorePreviousModel(ctx);
				persistState();
			}
			return;
		}

		if (!planModeEnabled || !ctx.hasUI) return;

		// Extract todos from last assistant message
		const lastAssistant = [...event.messages].reverse().find(isAssistantMessage);
		if (lastAssistant) {
			const extracted = extractTodoItems(getTextContent(lastAssistant));
			if (extracted.length > 0) todoItems = extracted;
		}

		if (todoItems.length === 0) return;
		persistState();

		const todoListText = todoItems.map((t, i) => `${i + 1}. ☐ ${t.text}`).join("\n");
		const planTodoListMessage = {
			customType: "plan-todo-list",
			content: `**Plan Steps (${todoItems.length}):**\n\n${todoListText}`,
			display: true,
		};

		const choice = await ctx.ui.select("Plan created. What next?", [
			"Execute the plan (switch to execution model)",
			"Stay in plan mode",
			"Refine the plan",
		]);

		if (choice?.startsWith("Execute")) {
			const firstTodoItem = todoItems[0];
			if (!firstTodoItem) return;

			planModeEnabled = false;
			executionMode = true;
			restoreNormalModeTools();
			updateStatus(ctx);
			persistState();

			// Switch to execution model
			if (executionModelId) await switchToModel(ctx, executionModelId, "execution");

			const remainingList = todoItems.map((t) => `${t.step}. ${t.text}`).join("\n");
			const execMessage = `Execute the plan.

Remaining steps:
${remainingList}

Start with: ${firstTodoItem.text}
After completing a step, include a [DONE:n] tag in your response.`;
			pi.sendMessage(planTodoListMessage, { deliverAs: "followUp" });
			pi.sendMessage(
				{ customType: "plan-mode-execute", content: execMessage, display: true },
				{ triggerTurn: true, deliverAs: "followUp" },
			);
		} else if (choice === "Refine the plan") {
			const refinement = await ctx.ui.editor("Refine the plan:", "");
			if (refinement?.trim()) {
				pi.sendMessage(planTodoListMessage, { deliverAs: "followUp" });
				pi.sendUserMessage(refinement.trim(), { deliverAs: "followUp" });
			}
		}
	});

	// Restore state on session start/resume
	pi.on("session_start", async (_event, ctx) => {
		if (pi.getFlag("plan") === true) planModeEnabled = true;

		const entries = ctx.sessionManager.getEntries();
		const planModeEntry = entries
			.filter((e: { type: string; customType?: string }) => e.type === "custom" && e.customType === "plan-mode")
			.pop() as { data?: PlanModeConfig } | undefined;

		if (planModeEntry?.data) {
			planModeEnabled = planModeEntry.data.enabled ?? planModeEnabled;
			todoItems = planModeEntry.data.todos ?? todoItems;
			executionMode = planModeEntry.data.executing ?? executionMode;
			toolsBeforePlanMode = planModeEntry.data.toolsBeforePlanMode ?? toolsBeforePlanMode;
			planningModelId = planModeEntry.data.planningModelId ?? planningModelId;
			executionModelId = planModeEntry.data.executionModelId ?? executionModelId;
			previousModelId = planModeEntry.data.previousModelId ?? previousModelId;
		}

		// On resume: re-scan messages to rebuild completion state
		const isResume = planModeEntry !== undefined;
		if (isResume && executionMode && todoItems.length > 0) {
			let executeIndex = -1;
			for (let i = entries.length - 1; i >= 0; i--) {
				const entry = entries[i] as { type: string; customType?: string };
				if (entry.customType === "plan-mode-execute") {
					executeIndex = i;
					break;
				}
			}
			const messages: AssistantMessage[] = [];
			for (let i = executeIndex + 1; i < entries.length; i++) {
				const entry = entries[i];
				if (entry.type === "message" && "message" in entry && isAssistantMessage(entry.message as AgentMessage)) {
					messages.push(entry.message as AssistantMessage);
				}
			}
			const allText = messages.map(getTextContent).join("\n");
			markCompletedSteps(allText, todoItems);
		}

		if (planModeEnabled) enablePlanModeTools();
		updateStatus(ctx);
	});
}
