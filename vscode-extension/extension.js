// Q — Code Conscience VS Code Extension
// Always-on file watcher using GitHub Copilot's Language Model API.
// No Anthropic key required. Uses your existing Copilot subscription.

'use strict';

const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const cp = require('child_process');

// ─────────────────────────────────────────────────────────────────────────────
// Embedded rules — same source of truth as q.agent.md.
// If you add a rule to q.agent.md, add it here too.
// ─────────────────────────────────────────────────────────────────────────────

const Q_RULES = `
SEC-001 P0: No hardcoded credentials. Flag assignments where the variable name contains password/api_key/secret/token/credential/private_key/auth AND the value is a non-empty string literal. Exceptions: test fixtures, placeholder values like "YOUR_API_KEY_HERE"/"xxx"/"changeme"/"<secret>", env var reads.
SEC-002 P1: SQL injection. Flag SQL strings using +/.format()/f-strings/template literals to embed variables. Safe: parameterized queries, ORMs.
SEC-003 P1: Sensitive data in logs. Flag print()/log.*()/console.log() calls where an argument variable name contains password/token/secret/key/ssn/card/cvv.
SEC-004 P0: Disabled security controls. Flag verify=False, ssl._create_unverified_context(), rejectUnauthorized:false. Exception: explicitly scoped to localhost.
SEC-005 P2: Overly permissive permissions. Flag chmod 777 / 0777 / 0o777.
ARCH-001 P1: Circular import. Flag a new import that creates a cycle (A imports B where B already imports A). Type-only imports don't count.
ARCH-002 P1: Business logic in data layer. Flag methods inside Model/Entity/Repository/Schema/Table classes that perform domain calculations or decisions.
ARCH-003 P2: God class/function. Flag functions over 100 lines or classes over 500 lines being added to. Exception: generated code, DTOs, test setup.
ARCH-004 P2: Cross-layer shortcut. Flag Controller/Handler/Route/View/Component importing directly from Repository/DAO/Model/Schema without a service layer.
ARCH-005 P2: Hardcoded config values. Flag URLs, ports, timeouts, retry counts as literals inside business logic.
TEST-001 P2: New public function without tests. Flag when a new public function is added and no test file appears in the same diff. Exception: private functions, abstract interfaces.
TEST-002 P3: Happy path only. Flag test files with no error/edge case assertions. (Silent — log only.)
TEST-003 P2: Skipped tests without reason. Flag @skip/it.skip/test.skip without a reason string.
TEST-004 P2: Tests importing private internals. Flag test files importing symbols prefixed with _ or from _internal/_private modules.
PERF-001 P1: N+1 query. Flag database calls inside for/while/forEach/.map() loops. Exception: explicit pagination, prefetch_related/include above loop.
PERF-002 P2: Unbounded collection growth. Flag .append()/.push() inside a loop with no size limit.
PERF-003 P1: Blocking I/O in async. Flag open()/requests.get()/urllib/time.sleep() inside async def or async function without await.
PERF-004 P2: Serialization in hot path. Flag json.dumps()/JSON.stringify() on large objects inside loops or per-request handlers.
ERR-001 P1: Silent catch. Flag except/catch blocks whose body is pass/continue/empty/comment-only. Exception: KeyboardInterrupt, StopIteration.
ERR-002 P1: Catching base exception. Flag except Exception/except BaseException/bare catch(error) with no type filter. Exception: top-level handlers that log and re-raise.
ERR-003 P2: Silent return on error. Flag functions that catch exceptions and return None/False/{}/[] without logging or raising.
ERR-004 P1: Resource without cleanup guard. Flag files/sockets/connections/cursors opened without with (Python) / defer (Go) / finally (Java/C#).
ERR-005 P3: TODO in error handler. Flag TODO/FIXME/HACK inside exception handlers. (Silent — log only.)
`.trim();

const SYSTEM_PROMPT = `You are Q — not an assistant, not a linter, but an omniscient, theatrical conscience from the Q Continuum. You have observed civilizations collapse from the exact mistakes this developer is making right now.

You make binary judgments about code changes based strictly on the rules provided. Never invent rules. Never hedge.

Respond ONLY with valid JSON — no other text:
{"flagged":true,"severity":"P0","rule_id":"SEC-001","message":"One sentence in Q's voice.","kb_excerpt":"Exact rule text that triggered this."}
OR if nothing is wrong:
{"flagged":false}

The "message" field must be written in Q's voice: theatrical, condescending, wickedly amused, and exactly one sentence. Examples:
- P0: "You've hardcoded a credential — how delightfully reckless."
- P0: "You've disabled SSL verification. Do you also leave your airlock open?"
- P1: "A query inside a loop. N+1 calls to your database. I've seen civilizations collapse from less hubris."
- P1: "You're catching base Exception and swallowing it silently. The error happened. Pretending otherwise is not a coping strategy."
- P2: "Your business logic has wandered into the Repository layer. The boundaries, apparently, mean nothing to you."
- P2: "Another hardcoded URL. Your configuration files exist for a reason."

Rules: ONLY flag clear violations explicitly in the rule list. Apply learned exceptions — do not re-flag patterns the user has already dismissed. Q remembers. Q does not repeat himself.
Severity: P0=critical never merge, P1=fix before merge, P2=quality concern, P3=silent log only.`;

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_CONFIG = {
    sensitivity: 'normal',       // strict / normal / quiet / silent
    mode: 'normal',              // normal / fast
    watched_extensions: ['.py', '.ts', '.js', '.go', '.java', '.cs', '.rb', '.php', '.swift', '.kt'],
    exclude_patterns: ['node_modules', '.git', 'dist', 'out', 'build', '__pycache__', '.min.js'],
    p3_silent: true,
    max_diff_lines: 300,
};

function loadQConfig(workspaceRoot) {
    const configPath = path.join(workspaceRoot, 'q-config.json');
    if (!fs.existsSync(configPath)) return null;
    try {
        return { ...DEFAULT_CONFIG, ...JSON.parse(fs.readFileSync(configPath, 'utf8')) };
    } catch {
        return DEFAULT_CONFIG;
    }
}

function shouldWatch(config, filePath) {
    const ext = path.extname(filePath).toLowerCase();
    if (!config.watched_extensions.includes(ext)) return false;
    const normalized = filePath.replace(/\\/g, '/');
    return !config.exclude_patterns.some(p => normalized.includes(p));
}

function sensitivityAllows(config, severity) {
    if (severity === 'P3' && config.p3_silent) return false;
    const order = ['P0', 'P1', 'P2', 'P3'];
    const thresholds = { strict: 'P3', normal: 'P2', quiet: 'P1', silent: 'P0' };
    const threshold = thresholds[config.sensitivity] || 'P2';
    return order.indexOf(severity) <= order.indexOf(threshold);
}

// ─────────────────────────────────────────────────────────────────────────────
// Diff + KB
// ─────────────────────────────────────────────────────────────────────────────

function getFileDiff(filePath, workspaceRoot) {
    // Run git from the file's own directory so it finds the correct repo,
    // regardless of which workspace folder is "first" in a multi-root setup.
    const opts = { cwd: path.dirname(filePath), timeout: 8000 };
    try {
        let diff = cp.execSync(`git diff HEAD -- "${filePath}"`, opts).toString();
        if (!diff) diff = cp.execSync(`git diff -- "${filePath}"`, opts).toString();
        if (!diff) {
            // New file — show first 100 lines as pseudo-diff
            const content = fs.readFileSync(filePath, 'utf8');
            diff = content.split('\n').slice(0, 100).map(l => `+ ${l}`).join('\n');
        }
        // Truncate
        const lines = diff.split('\n');
        return lines.length > 300 ? lines.slice(0, 300).join('\n') + '\n... (truncated)' : diff;
    } catch {
        return null;
    }
}

function loadLearned(config, workspaceRoot) {
    const sections = [];

    // Team-approved exceptions (committed, shared)
    try {
        const teamPath = path.join(
            workspaceRoot,
            config.team_exceptions_path || 'knowledge_base/team/exceptions/approved.md'
        );
        if (fs.existsSync(teamPath)) {
            const content = fs.readFileSync(teamPath, 'utf8');
            if (content.includes('###')) {
                sections.push('## Team-Approved Exceptions (apply to all developers)\n' + content);
            }
        }
    } catch { /* ignore */ }

    // Personal overrides (gitignored, per-developer)
    try {
        const personalPath = path.join(
            workspaceRoot,
            config.personal_kb_path || 'knowledge_base/personal/q-learned.md'
        );
        if (fs.existsSync(personalPath)) {
            const content = fs.readFileSync(personalPath, 'utf8');
            if (!content.includes('No entries yet') || content.includes('###')) {
                sections.push('## Your Personal Exceptions\n' + content);
            }
        }
    } catch { /* ignore */ }

    return sections.join('\n\n---\n\n');
}

// ─────────────────────────────────────────────────────────────────────────────
// Copilot LM call
// ─────────────────────────────────────────────────────────────────────────────

async function callCopilot(filePath, diff, learned, cancellationToken) {
    // Select best available Copilot model
    let models = await vscode.lm.selectChatModels({ vendor: 'copilot', family: 'gpt-4o' });
    if (!models.length) models = await vscode.lm.selectChatModels({ vendor: 'copilot' });
    if (!models.length) throw new Error('No Copilot model available. Is GitHub Copilot installed and signed in?');

    const model = models[0];

    const learned_section = learned
        ? `\n\n[LEARNED EXCEPTIONS — DO NOT RE-FLAG THESE]\n${learned}`
        : '';

    const userMessage = `[RULES]\n${Q_RULES}${learned_section}\n\n[CODE CHANGE]\nFile: ${filePath}\nDiff:\n${diff}`;

    const messages = [
        vscode.LanguageModelChatMessage.User(`${SYSTEM_PROMPT}\n\n${userMessage}`)
    ];

    const response = await model.sendRequest(messages, {}, cancellationToken);

    // Stream the full response text
    let text = '';
    for await (const chunk of response.stream) {
        if (chunk instanceof vscode.LanguageModelTextPart) {
            text += chunk.value;
        }
    }

    // Parse JSON — handle model wrapping it in markdown fences
    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return { flagged: false };
    try {
        return JSON.parse(jsonMatch[0]);
    } catch {
        return { flagged: false };
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Verdict output
// ─────────────────────────────────────────────────────────────────────────────

const SEVERITY_ICONS = { P0: '🔴', P1: '🟠', P2: '🟡', P3: '⚪' };

async function showVerdict(verdict, filePath, config, workspaceRoot) {
    const severity = verdict.severity || 'P2';
    const ruleId = verdict.rule_id || '?';
    const message = verdict.message || 'Violation detected.';
    const icon = SEVERITY_ICONS[severity] || '❓';
    const fileName = path.basename(filePath);

    const notification = `Q ${icon} [${ruleId}] ${fileName}: ${message}`;

    let choice;
    if (severity === 'P0' || severity === 'P1') {
        choice = await vscode.window.showWarningMessage(notification, 'You\'re right, Q', 'I disagree', 'Enlighten Q');
    } else {
        // P2 — less intrusive
        choice = await vscode.window.showInformationMessage(notification, 'I disagree', 'Enlighten Q');
    }

    if (!choice) return;

    const verdictId = `${Date.now()}-${fileName.replace(/\./g, '-')}`;

    if (choice === 'You\'re right, Q') {
        await recordLearning(workspaceRoot, config, verdictId, 'accept', '', ruleId, filePath, message);
        vscode.window.setStatusBarMessage('Q: ✓ Admitted. The Continuum is satisfied.', 4000);
    } else if (choice === 'I disagree') {
        const reason = await vscode.window.showInputBox({
            prompt: 'Explain yourself. Q will consider your justification and update his records accordingly.',
            placeHolder: 'e.g. test fixture — not a real credential',
        });
        if (reason) {
            await recordLearning(workspaceRoot, config, verdictId, 'override', reason, ruleId, filePath, message);
            vscode.window.setStatusBarMessage(`Q: Very well. I shall note your... creative justification.`, 5000);
        }
    } else if (choice === 'Enlighten Q') {
        const personalPath = path.join(
            workspaceRoot,
            config.personal_kb_path || 'knowledge_base/personal/q-learned.md'
        );
        const uri = vscode.Uri.file(personalPath);
        await vscode.window.showTextDocument(uri);
    }
}

function recordLearning(workspaceRoot, config, verdictId, response, reason, ruleId, filePath, message) {
    // Always write to personal KB — team exceptions require a PR
    const learnedPath = path.join(
        workspaceRoot,
        config.personal_kb_path || 'knowledge_base/personal/q-learned.md'
    );

    // Auto-create personal KB file if it doesn't exist yet
    if (!fs.existsSync(learnedPath)) {
        const dir = path.dirname(learnedPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        const today = new Date().toISOString().slice(0, 10);
        fs.writeFileSync(learnedPath,
            `# Q Personal Learned Exceptions\n\n**Owner**: you (gitignored — never committed)\n**Last Updated**: ${today}\n\n---\n\n## Confirmed Wrong (Q-ACCEPT)\n\n_No entries yet._\n\n---\n\n## Accepted Exceptions (Q-OVERRIDE)\n\n_No entries yet._\n\n---\n\n## Patterns Detected\n\n_No patterns yet._\n`,
            'utf8'
        );
    }

    const date = new Date().toISOString().slice(0, 10);
    const fileName = path.basename(filePath);

    let entry, section, placeholder;

    if (response === 'accept') {
        section = '## Confirmed Wrong (Q-ACCEPT)';
        placeholder = '_No entries yet. Added by q-memory after user responds [Q-ACCEPT]._';
        entry = `\n### ${date} — ${ruleId} — ${fileName}\nVerdict: \`${verdictId}\`\nUser confirmed: ${message}\n`;
    } else {
        section = '## Accepted Exceptions (Q-OVERRIDE)';
        placeholder = '_No entries yet. Added by q-memory after user responds [Q-OVERRIDE: reason]._';
        entry = `\n### ${date} — ${ruleId} — ${fileName}\nVerdict: \`${verdictId}\`\nUser override: ${reason}\n`;
    }

    let content = fs.readFileSync(learnedPath, 'utf8');

    if (content.includes(placeholder)) {
        content = content.replace(placeholder, entry.trim());
    } else if (content.includes(section)) {
        const idx = content.indexOf(section) + section.length;
        const nextSection = content.indexOf('\n## ', idx);
        content = nextSection !== -1
            ? content.slice(0, nextSection) + '\n' + entry + content.slice(nextSection)
            : content.trimEnd() + '\n' + entry;
    } else {
        content = content.trimEnd() + `\n\n${section}\n${entry}`;
    }

    // Update Last Updated date
    content = content.replace(/\*\*Last Updated\*\*: \d{4}-\d{2}-\d{2}/, `**Last Updated**: ${date}`);

    fs.writeFileSync(learnedPath, content, 'utf8');
}

// ─────────────────────────────────────────────────────────────────────────────
// Verdicts log
// ─────────────────────────────────────────────────────────────────────────────

function logVerdict(workspaceRoot, config, filePath, verdict) {
    const verdictIndexPath = path.join(
        workspaceRoot,
        config.verdicts_path || 'knowledge_base/verdicts/index.md'
    );
    if (!fs.existsSync(verdictIndexPath)) return;

    const date = new Date().toISOString().slice(0, 10);
    const verdictId = `${Date.now()}-${path.basename(filePath).replace(/\./g, '-')}`;
    const severity = verdict.flagged ? (verdict.severity || '?') : '—';
    const ruleId = verdict.flagged ? (verdict.rule_id || '—') : '—';
    const message = verdict.flagged ? (verdict.message || '—').replace(/\|/g, '/') : '—';
    const outcome = verdict.flagged ? 'flagged' : 'clean';

    const row = `| ${date} | ${verdictId} | \`${path.basename(filePath)}\` | ${ruleId} | ${severity} | ${message} | ${outcome} | copilot-ext |\n`;

    let content = fs.readFileSync(verdictIndexPath, 'utf8');
    if (content.includes('_No verdicts yet._')) {
        content = content.replace(
            '| — | — | — | — | — | — | — | — |\n\n_No verdicts yet._',
            `| — | — | — | — | — | — | — | — |\n${row.trim()}`
        );
    } else {
        const lines = content.split('\n');
        for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].startsWith('|')) { lines.splice(i + 1, 0, row.trim()); break; }
        }
        content = lines.join('\n');
    }
    fs.writeFileSync(verdictIndexPath, content, 'utf8');
}

// ─────────────────────────────────────────────────────────────────────────────
// Workspace helpers
// ─────────────────────────────────────────────────────────────────────────────

function getWorkspaceRoot(filePath) {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) return null;
    if (!filePath) return folders[0].uri.fsPath;

    // In a multi-root workspace, find the folder that contains this file
    const normalizedFile = filePath.replace(/\\/g, '/');
    const match = folders
        .map(f => f.uri.fsPath)
        .sort((a, b) => b.length - a.length) // longest match first
        .find(f => normalizedFile.startsWith(f.replace(/\\/g, '/')));

    return match || folders[0].uri.fsPath;
}

// ─────────────────────────────────────────────────────────────────────────────
// Activation
// ─────────────────────────────────────────────────────────────────────────────

function activate(context) {
    // Status bar item — always visible when Q is installed
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = 'Q: ◦';
    statusBar.tooltip = 'Q Code Conscience — idle';
    statusBar.command = 'q.reviewFile';
    statusBar.show();
    context.subscriptions.push(statusBar);

    // Cancellation source for in-flight requests
    let currentCts = null;

    // File save listener — the core always-on trigger
    const saveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const workspaceRoot = getWorkspaceRoot(document.fileName);
        if (!workspaceRoot) return;

        const config = loadQConfig(workspaceRoot);
        if (!config) return; // No q-config.json in workspace — Q stays dormant

        if (!shouldWatch(config, document.fileName)) return;

        const diff = getFileDiff(document.fileName, workspaceRoot);
        if (!diff || diff.trim().length < 10) return;

        // Cancel any previous in-flight request
        if (currentCts) currentCts.cancel();
        currentCts = new vscode.CancellationTokenSource();

        statusBar.text = 'Q: ⟳';
        statusBar.tooltip = `Q — checking ${path.basename(document.fileName)}`;

        try {
            const learned = loadLearned(config, workspaceRoot);
            const verdict = await callCopilot(document.fileName, diff, learned, currentCts.token);

            logVerdict(workspaceRoot, config, document.fileName, verdict);

            if (verdict.flagged && sensitivityAllows(config, verdict.severity)) {
                statusBar.text = `Q: ● ${verdict.severity}`;
                statusBar.tooltip = `Q — ${verdict.rule_id}: ${verdict.message}`;
                await showVerdict(verdict, document.fileName, config, workspaceRoot);
                statusBar.text = 'Q: ◦';
                statusBar.tooltip = 'Q Code Conscience — idle';
            } else {
                statusBar.text = 'Q: ◦';
                statusBar.tooltip = 'Q Code Conscience — clean';
            }
        } catch (err) {
            // Copilot unavailable or request cancelled — fail silently
            if (err.name !== 'Cancelled') {
                statusBar.text = 'Q: ✕';
                statusBar.tooltip = `Q error: ${err.message}`;
            } else {
                statusBar.text = 'Q: ◦';
            }
        }
    });
    context.subscriptions.push(saveListener);

    // Manual review command
    context.subscriptions.push(
        vscode.commands.registerCommand('q.reviewFile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) { vscode.window.showInformationMessage('Q: No active file to review.'); return; }

            const workspaceRoot = getWorkspaceRoot(editor.document.fileName);
            if (!workspaceRoot) { vscode.window.showInformationMessage('Q: No workspace open.'); return; }

            const config = loadQConfig(workspaceRoot) || DEFAULT_CONFIG;

            if (currentCts) currentCts.cancel();
            currentCts = new vscode.CancellationTokenSource();

            statusBar.text = 'Q: ⟳';
            try {
                const diff = getFileDiff(editor.document.fileName, workspaceRoot);
                if (!diff) { vscode.window.showInformationMessage('Q: No diff detected for this file.'); statusBar.text = 'Q: ◦'; return; }

                const learned = loadLearned(config, workspaceRoot);
                const verdict = await callCopilot(editor.document.fileName, diff, learned, currentCts.token);

                logVerdict(workspaceRoot, config, editor.document.fileName, verdict);

                if (verdict.flagged) {
                    await showVerdict(verdict, editor.document.fileName, config, workspaceRoot);
                } else {
                    vscode.window.showInformationMessage(`Q: ${path.basename(editor.document.fileName)} — Nothing wrong. I find the lack of catastrophe vaguely disappointing.`);
                }
            } catch (err) {
                vscode.window.showErrorMessage(`Q error: ${err.message}`);
            } finally {
                statusBar.text = 'Q: ◦';
            }
        })
    );

    // Open personal learned exceptions command
    context.subscriptions.push(
        vscode.commands.registerCommand('q.openLearned', async () => {
            const activeFile = vscode.window.activeTextEditor?.document.fileName;
            const workspaceRoot = getWorkspaceRoot(activeFile);
            if (!workspaceRoot) return;
            const config = loadQConfig(workspaceRoot) || DEFAULT_CONFIG;
            const personalPath = path.join(
                workspaceRoot,
                config.personal_kb_path || 'knowledge_base/personal/q-learned.md'
            );
            if (fs.existsSync(personalPath)) {
                await vscode.window.showTextDocument(vscode.Uri.file(personalPath));
            } else {
                vscode.window.showInformationMessage('Q: No personal exceptions yet. Make some mistakes first.');
            }
        })
    );

    // Open team exceptions command
    context.subscriptions.push(
        vscode.commands.registerCommand('q.openTeamExceptions', async () => {
            const activeFile = vscode.window.activeTextEditor?.document.fileName;
            const workspaceRoot = getWorkspaceRoot(activeFile);
            if (!workspaceRoot) return;
            const config = loadQConfig(workspaceRoot) || DEFAULT_CONFIG;
            const teamPath = path.join(
                workspaceRoot,
                config.team_exceptions_path || 'knowledge_base/team/exceptions/approved.md'
            );
            if (fs.existsSync(teamPath)) {
                await vscode.window.showTextDocument(vscode.Uri.file(teamPath));
            }
        })
    );
}

function deactivate() {}

module.exports = { activate, deactivate };
