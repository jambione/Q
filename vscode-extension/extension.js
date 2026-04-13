// Q — Code Conscience VS Code Extension
// v0.2.0 — debounce, diff cache, pre-filter, model tiering, inline diagnostics,
//           rate limiting, path-aware learning, auto-suggest, false-negative signal
//
// No Anthropic key required. Uses your existing Copilot subscription.

'use strict';

const vscode = require('vscode');
const path = require('path');
const fs = require('fs');
const cp = require('child_process');
const crypto = require('crypto');

// ─────────────────────────────────────────────────────────────────────────────
// Embedded rules — same source of truth as q.agent.md.
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
{"flagged":true,"severity":"P0","rule_id":"SEC-001","message":"One sentence in Q's voice.","kb_excerpt":"Exact rule text that triggered this.","line_number":42}
OR if nothing is wrong:
{"flagged":false}

The "line_number" field is the 1-based line in the file where the violation occurs. Include it when you can determine it from the diff context. Omit if unknown.

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
// Pre-filter: high-signal keywords that indicate a likely violation
// If NONE of these appear in the added lines, skip the API call entirely.
// ─────────────────────────────────────────────────────────────────────────────

const HIGH_SIGNAL_KEYWORDS = [
    // SEC: credentials
    'password', 'api_key', 'apikey', 'secret', 'token', 'credential', 'private_key',
    // SEC: security controls
    'verify=False', 'verify = False', 'rejectUnauthorized', 'ssl._create_unverified', '0777', '0o777', 'chmod',
    // SEC: SQL
    '" + ', "' + ", 'execute(', 'cursor.execute', 'SELECT ', 'INSERT ', 'UPDATE ', 'DELETE ',
    // ERR: silent catches
    'except Exception', 'except BaseException', 'except:', ': pass',
    // PERF: blocking I/O
    'requests.get(', 'requests.post(', 'time.sleep(', 'urllib.request',
    // TEST: skips
    '@skip', '@pytest.mark.skip', 'it.skip(', 'test.skip(', 'xit(',
    // ERR/ARCH
    'TODO', 'FIXME', 'HACK',
];

// Separate list: keywords that indicate HIGH risk — use best model
const CRITICAL_KEYWORDS = [
    'password', 'api_key', 'apikey', 'secret', 'token', 'credential',
    'verify=False', 'rejectUnauthorized', 'ssl._create_unverified',
    'execute(', 'cursor.execute',
];

// ─────────────────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────────────────

const DEFAULT_CONFIG = {
    sensitivity: 'normal',
    mode: 'normal',
    watched_extensions: ['.py', '.ts', '.js', '.go', '.java', '.cs', '.rb', '.php', '.swift', '.kt'],
    exclude_patterns: ['node_modules', '.git', 'dist', 'out', 'build', '__pycache__', '.min.js'],
    p3_silent: true,
    max_diff_lines: 350,
    rate_limit_per_minute: 10,
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
// Pre-filter: classify diff before touching the API
// Returns: 'skip' | 'standard' | 'critical'
// ─────────────────────────────────────────────────────────────────────────────

function classifyDiff(diff) {
    // Extract only lines being added (not context or removals)
    const addedLines = diff.split('\n')
        .filter(l => l.startsWith('+') && !l.startsWith('+++'))
        .map(l => l.slice(1).trim())
        .filter(l => l && !l.startsWith('#') && !l.startsWith('//') && !l.startsWith('*'));

    // No meaningful code additions → safe to skip entirely
    if (addedLines.length === 0) return 'skip';

    const joined = addedLines.join('\n');

    if (CRITICAL_KEYWORDS.some(kw => joined.includes(kw))) return 'critical';
    if (HIGH_SIGNAL_KEYWORDS.some(kw => joined.includes(kw))) return 'standard';
    return 'skip';
}

// ─────────────────────────────────────────────────────────────────────────────
// Rate limiter
// ─────────────────────────────────────────────────────────────────────────────

const callTimestamps = [];

function checkRateLimit(config) {
    const limit = config.rate_limit_per_minute || 10;
    const now = Date.now();
    const windowStart = now - 60000;
    while (callTimestamps.length && callTimestamps[0] < windowStart) callTimestamps.shift();
    if (callTimestamps.length >= limit) return false;
    callTimestamps.push(now);
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Diff cache: skip API call if diff hasn't changed since last verdict
// ─────────────────────────────────────────────────────────────────────────────

const verdictCache = new Map(); // filePath -> { hash, verdict }

function hashString(str) {
    return crypto.createHash('md5').update(str).digest('hex').slice(0, 12);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dismiss tracker: auto-suggest path exception after N dismissals
// ─────────────────────────────────────────────────────────────────────────────

const AUTO_SUGGEST_THRESHOLD = 3;
let dismissCounts; // Map loaded from workspaceState in activate()

function getDirPattern(filePath) {
    const parts = filePath.replace(/\\/g, '/').split('/');
    if (parts.length <= 1) return null;
    // Return the first 2-3 directory levels as a pattern
    const meaningful = parts.slice(0, -1).filter(p => !p.match(/^[A-Z]:/));
    return meaningful.length > 0 ? meaningful.join('/') + '/**' : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Diff — with context, untracked file guard
// ─────────────────────────────────────────────────────────────────────────────

function getFileDiff(filePath) {
    const opts = { cwd: path.dirname(filePath), timeout: 8000 };
    try {
        // Skip untracked files — no git history means no meaningful diff context
        const status = cp.execSync(`git status --porcelain -- "${filePath}"`, opts).toString().trim();
        if (status.startsWith('??')) return null;

        // -U30: 30 lines of context so Q can see surrounding code (hot paths, class boundaries, etc.)
        let diff = cp.execSync(`git diff -U30 HEAD -- "${filePath}"`, opts).toString();
        if (!diff) diff = cp.execSync(`git diff -U30 -- "${filePath}"`, opts).toString();
        if (!diff) diff = cp.execSync(`git diff -U30 --cached -- "${filePath}"`, opts).toString();
        if (!diff) return null;

        const lines = diff.split('\n');
        if (lines.length > 350) {
            const half = 175;
            return lines.slice(0, half).join('\n')
                + `\n\n... (${lines.length - 350} lines omitted) ...\n\n`
                + lines.slice(-half).join('\n');
        }
        return diff;
    } catch {
        return null;
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Two-tier exception loading
// ─────────────────────────────────────────────────────────────────────────────

function loadLearned(config, workspaceRoot) {
    const sections = [];

    try {
        const teamPath = path.join(workspaceRoot, config.team_exceptions_path || 'knowledge_base/team/exceptions/approved.md');
        if (fs.existsSync(teamPath)) {
            const content = fs.readFileSync(teamPath, 'utf8');
            if (content.includes('###')) {
                sections.push('## Team-Approved Exceptions (apply to all developers)\n' + content);
            }
        }
    } catch { /* ignore */ }

    try {
        const personalPath = path.join(workspaceRoot, config.personal_kb_path || 'knowledge_base/personal/q-learned.md');
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
// Copilot LM call — model tiering based on risk classification
// ─────────────────────────────────────────────────────────────────────────────

async function selectModel(riskLevel) {
    // Critical risk: use best available model
    // Standard risk: try a faster model first
    const preferredFamilies = riskLevel === 'critical'
        ? ['gpt-4o', 'gpt-4-turbo', 'gpt-4', 'claude-sonnet']
        : ['gpt-4o-mini', 'gpt-3.5-turbo', 'gpt-4o', 'gpt-4'];

    for (const family of preferredFamilies) {
        const models = await vscode.lm.selectChatModels({ vendor: 'copilot', family });
        if (models.length > 0) return models[0];
    }
    // Final fallback: any copilot model
    const models = await vscode.lm.selectChatModels({ vendor: 'copilot' });
    if (models.length > 0) return models[0];
    throw new Error('No Copilot model available. Is GitHub Copilot installed and signed in?');
}

async function callCopilot(filePath, diff, learned, riskLevel, cancellationToken) {
    const model = await selectModel(riskLevel);

    const learnedSection = learned
        ? `\n\n[LEARNED EXCEPTIONS — DO NOT RE-FLAG THESE]\n${learned}`
        : '';

    const userMessage = `[RULES]\n${Q_RULES}${learnedSection}\n\n[CODE CHANGE]\nFile: ${filePath}\nDiff:\n${diff}`;
    const messages = [vscode.LanguageModelChatMessage.User(`${SYSTEM_PROMPT}\n\n${userMessage}`)];

    const response = await model.sendRequest(messages, {}, cancellationToken);

    let text = '';
    for await (const chunk of response.stream) {
        if (chunk instanceof vscode.LanguageModelTextPart) text += chunk.value;
    }

    const jsonMatch = text.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return { flagged: false };
    try {
        return JSON.parse(jsonMatch[0]);
    } catch {
        return { flagged: false };
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Inline diagnostics
// ─────────────────────────────────────────────────────────────────────────────

const DIAGNOSTIC_SEVERITY = {
    P0: vscode.DiagnosticSeverity.Error,
    P1: vscode.DiagnosticSeverity.Error,
    P2: vscode.DiagnosticSeverity.Warning,
    P3: vscode.DiagnosticSeverity.Information,
};

function updateDiagnostics(diagnosticCollection, filePath, verdict) {
    const uri = vscode.Uri.file(filePath);

    if (!verdict.flagged) {
        diagnosticCollection.set(uri, []); // clear any previous squiggle
        return;
    }

    let lineNumber = 0;

    // Use LLM-reported line number if available (1-based → 0-based)
    if (verdict.line_number && verdict.line_number > 0) {
        lineNumber = verdict.line_number - 1;
    } else {
        // Infer from the diff: find the first added line's target line number
        try {
            const content = fs.readFileSync(filePath, 'utf8').split('\n');
            const message = verdict.message || '';
            // Try to find a line in the file matching keywords from the message
            // (best-effort — fall back to line 0 if not found)
            const keywords = (verdict.rule_id || '').split('-')[0].toLowerCase();
            lineNumber = content.findIndex(l => l.toLowerCase().includes(keywords));
            if (lineNumber < 0) lineNumber = 0;
        } catch { lineNumber = 0; }
    }

    const range = new vscode.Range(lineNumber, 0, lineNumber, Number.MAX_SAFE_INTEGER);
    const severity = DIAGNOSTIC_SEVERITY[verdict.severity] || vscode.DiagnosticSeverity.Warning;
    const diag = new vscode.Diagnostic(
        range,
        `Q [${verdict.rule_id}]: ${verdict.message}`,
        severity
    );
    diag.source = 'Q';
    diag.code = verdict.rule_id;

    diagnosticCollection.set(uri, [diag]);
}

// ─────────────────────────────────────────────────────────────────────────────
// Verdict output + learning
// ─────────────────────────────────────────────────────────────────────────────

const SEVERITY_ICONS = { P0: '🔴', P1: '🟠', P2: '🟡', P3: '⚪' };

async function showVerdict(verdict, filePath, config, workspaceRoot, context) {
    const severity = verdict.severity || 'P2';
    const ruleId = verdict.rule_id || '?';
    const message = verdict.message || 'Violation detected.';
    const icon = SEVERITY_ICONS[severity] || '❓';
    const fileName = path.basename(filePath);

    const notification = `Q ${icon} [${ruleId}] ${fileName}: ${message}`;
    const verdictId = makeVerdictId(filePath);

    let choice;
    if (severity === 'P0' || severity === 'P1') {
        choice = await vscode.window.showWarningMessage(notification, "You're right, Q", 'I disagree', 'Enlighten Q');
    } else {
        choice = await vscode.window.showInformationMessage(notification, 'I disagree', 'Enlighten Q');
    }

    if (!choice) return;

    if (choice === "You're right, Q") {
        await recordLearning(workspaceRoot, config, verdictId, 'accept', '', ruleId, filePath, message);
        vscode.window.setStatusBarMessage('Q: ✓ Admitted. The Continuum is satisfied.', 4000);

    } else if (choice === 'I disagree') {
        const reason = await vscode.window.showInputBox({
            prompt: 'Explain yourself. Q will consider your justification.',
            placeHolder: 'e.g. test fixture — not a real credential',
        });
        if (reason) {
            await recordLearning(workspaceRoot, config, verdictId, 'override', reason, ruleId, filePath, message);
            vscode.window.setStatusBarMessage('Q: Very well. I shall note your... creative justification.', 5000);
            checkAutoSuggest(ruleId, filePath, context);
        }

    } else if (choice === 'Enlighten Q') {
        const personalPath = path.join(workspaceRoot, config.personal_kb_path || 'knowledge_base/personal/q-learned.md');
        if (fs.existsSync(personalPath)) {
            await vscode.window.showTextDocument(vscode.Uri.file(personalPath));
        }
    }
}

async function showCleanVerdict(filePath) {
    const fileName = path.basename(filePath);
    const choice = await vscode.window.showInformationMessage(
        `Q: ${fileName} — Nothing wrong. I find the lack of catastrophe vaguely disappointing.`,
        'Q missed something'
    );
    if (choice === 'Q missed something') {
        const issue = await vscode.window.showInputBox({
            prompt: 'What did Q miss? Describe the violation so the rulebook can be improved.',
            placeHolder: 'e.g. There is an N+1 query on line 42 inside the for loop',
        });
        if (issue) {
            const activeFile = vscode.window.activeTextEditor?.document.fileName;
            const workspaceRoot = getWorkspaceRoot(activeFile);
            vscode.window.showInformationMessage(
                `Q: Noted. Consider opening a rule proposal PR — see docs/rule-governance.md.`,
                'Open governance docs'
            ).then(sel => {
                if (sel === 'Open governance docs' && workspaceRoot) {
                    const govDoc = path.join(workspaceRoot, 'docs', 'rule-governance.md');
                    if (fs.existsSync(govDoc)) {
                        vscode.window.showTextDocument(vscode.Uri.file(govDoc));
                    } else {
                        vscode.window.showInformationMessage('Q: docs/rule-governance.md not found in this workspace.');
                    }
                }
            });
        }
    }
}

function checkAutoSuggest(ruleId, filePath, context) {
    const dirPattern = getDirPattern(filePath);
    if (!dirPattern) return;

    const key = `${ruleId}:${dirPattern}`;
    const counts = context.workspaceState.get('q.dismissCounts') || {};
    counts[key] = (counts[key] || 0) + 1;
    context.workspaceState.update('q.dismissCounts', counts);

    if (counts[key] === AUTO_SUGGEST_THRESHOLD) {
        vscode.window.showInformationMessage(
            `Q: You've dismissed ${ruleId} in "${dirPattern}" ${AUTO_SUGGEST_THRESHOLD} times. Add a path exception?`,
            'Add exception', 'Ignore'
        ).then(choice => {
            if (choice === 'Add exception') {
                vscode.window.showInputBox({
                    prompt: `Add a path exception for ${ruleId} in ${dirPattern}`,
                    value: `Files in ${dirPattern} are exempt from ${ruleId}`,
                }).then(reason => {
                    if (reason) {
                        // Open terminal with the q-learn command pre-filled
                        const terminal = vscode.window.createTerminal('Q — Add Exception');
                        terminal.show();
                        terminal.sendText(
                            `python scripts/q-learn.py --verdict-id auto-suggest --response override --reason "${reason.replace(/"/g, '\\"')}"`,
                            false
                        );
                    }
                });
            }
        });
    }
}

function recordLearning(workspaceRoot, config, verdictId, response, reason, ruleId, filePath, message) {
    const learnedPath = path.join(
        workspaceRoot,
        config.personal_kb_path || 'knowledge_base/personal/q-learned.md'
    );

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

    // Path-aware: record the relative directory pattern, not just the filename
    const dirPattern = getDirPattern(filePath);
    const pathNote = dirPattern ? `\nPath pattern: \`${dirPattern}\`` : '';

    let entry, section, placeholder;

    if (response === 'accept') {
        section = '## Confirmed Wrong (Q-ACCEPT)';
        placeholder = '_No entries yet. Added by q-memory after user responds [Q-ACCEPT]._';
        entry = `\n### ${date} — ${ruleId} — ${fileName}\nVerdict: \`${verdictId}\`\nUser confirmed: ${message}\n`;
    } else {
        section = '## Accepted Exceptions (Q-OVERRIDE)';
        placeholder = '_No entries yet. Added by q-memory after user responds [Q-OVERRIDE: reason]._';
        entry = `\n### ${date} — ${ruleId} — ${fileName}\nVerdict: \`${verdictId}\`\nUser override: ${reason}${pathNote}\n`;
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

    content = content.replace(/\*\*Last Updated\*\*: \d{4}-\d{2}-\d{2}/, `**Last Updated**: ${date}`);
    fs.writeFileSync(learnedPath, content, 'utf8');
}

// ─────────────────────────────────────────────────────────────────────────────
// Verdicts log
// ─────────────────────────────────────────────────────────────────────────────

function logVerdict(workspaceRoot, config, filePath, verdict) {
    const verdictIndexPath = path.join(workspaceRoot, config.verdicts_path || 'knowledge_base/verdicts/index.md');
    if (!fs.existsSync(verdictIndexPath)) return;

    const date = new Date().toISOString().slice(0, 10);
    const verdictId = makeVerdictId(filePath);
    const severity = verdict.flagged ? (verdict.severity || '?') : '—';
    const ruleId = verdict.flagged ? (verdict.rule_id || '—') : '—';
    const message = verdict.flagged ? (verdict.message || '—').replace(/\|/g, '/') : '—';
    const outcome = verdict.flagged ? 'flagged' : 'clean';

    const row = `| ${date} | ${verdictId} | \`${path.basename(filePath)}\` | ${ruleId} | ${severity} | ${message} | ${outcome} | copilot-ext |`;

    let content = fs.readFileSync(verdictIndexPath, 'utf8');
    if (content.includes('_No verdicts yet._')) {
        content = content.replace(
            '| — | — | — | — | — | — | — | — |\n\n_No verdicts yet._',
            `| — | — | — | — | — | — | — | — |\n${row}`
        );
    } else {
        const lines = content.split('\n');
        for (let i = lines.length - 1; i >= 0; i--) {
            if (lines[i].startsWith('|')) { lines.splice(i + 1, 0, row); break; }
        }
        content = lines.join('\n');
    }
    fs.writeFileSync(verdictIndexPath, content, 'utf8');
}

// ─────────────────────────────────────────────────────────────────────────────
// Multi-root workspace: find the folder that owns this file
// ─────────────────────────────────────────────────────────────────────────────

function getWorkspaceRoot(filePath) {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders || folders.length === 0) return null;
    if (!filePath) return folders[0].uri.fsPath;

    const normalizedFile = filePath.replace(/\\/g, '/');
    const match = folders
        .map(f => f.uri.fsPath)
        .sort((a, b) => b.length - a.length)
        .find(f => normalizedFile.startsWith(f.replace(/\\/g, '/')));

    return match || folders[0].uri.fsPath;
}

// ─────────────────────────────────────────────────────────────────────────────
// Verdict ID generator — second-precision timestamp + counter for uniqueness
// ─────────────────────────────────────────────────────────────────────────────

let _verdictCounter = 0;
function makeVerdictId(filePath) {
    const ts = new Date().toISOString().replace(/[-T:]/g, '').slice(0, 15); // YYYYMMDDHHmmSS
    const n = String(++_verdictCounter).padStart(3, '0');
    const base = path.basename(filePath).replace(/\./g, '-');
    return `${ts}-${n}-${base}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Activation
// ─────────────────────────────────────────────────────────────────────────────

function activate(context) {
    // Inline diagnostic squiggles
    const diagnosticCollection = vscode.languages.createDiagnosticCollection('q');
    context.subscriptions.push(diagnosticCollection);

    // Status bar
    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBar.text = 'Q: ◦';
    statusBar.tooltip = 'Q Code Conscience — idle';
    statusBar.command = 'q.reviewFile';
    statusBar.show();
    context.subscriptions.push(statusBar);

    // One-time Copilot availability check — fail visibly, not silently
    vscode.lm.selectChatModels({ vendor: 'copilot' }).then(models => {
        if (models.length === 0) {
            statusBar.text = 'Q: ✕';
            statusBar.tooltip = 'Q — GitHub Copilot not found';
            vscode.window.showWarningMessage(
                'Q: GitHub Copilot is not available. Install the GitHub Copilot extension and sign in to activate Q.',
                'Open Extensions'
            ).then(choice => {
                if (choice === 'Open Extensions') {
                    vscode.commands.executeCommand('workbench.extensions.search', 'GitHub.copilot-chat');
                }
            });
        }
    });

    let currentCts = null;
    let debounceTimer = null;

    // ── File save listener ──────────────────────────────────────────────────
    const saveListener = vscode.workspace.onDidSaveTextDocument(async (document) => {
        const workspaceRoot = getWorkspaceRoot(document.fileName);
        if (!workspaceRoot) return;

        const config = loadQConfig(workspaceRoot);
        if (!config) return;

        if (!shouldWatch(config, document.fileName)) return;

        // Debounce: wait 1.5s after last save before firing
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {

            const diff = getFileDiff(document.fileName);
            if (!diff) return; // untracked file or no changes

            // Pre-filter: skip if no meaningful code changes
            const riskLevel = classifyDiff(diff);
            if (riskLevel === 'skip') return;

            // Diff cache: skip if verdict already known for this exact diff
            const diffHash = hashString(diff);
            const cached = verdictCache.get(document.fileName);
            if (cached && cached.hash === diffHash) {
                // Re-apply cached diagnostics without an API call
                if (cached.verdict.flagged && sensitivityAllows(config, cached.verdict.severity)) {
                    updateDiagnostics(diagnosticCollection, document.fileName, cached.verdict);
                }
                return;
            }

            // Rate limit
            if (!checkRateLimit(config)) {
                statusBar.text = 'Q: ◦';
                statusBar.tooltip = 'Q — rate limit reached, check skipped';
                return;
            }

            if (currentCts) currentCts.cancel();
            currentCts = new vscode.CancellationTokenSource();

            statusBar.text = 'Q: ⟳';
            statusBar.tooltip = `Q — checking ${path.basename(document.fileName)} [${riskLevel}]`;

            try {
                const learned = loadLearned(config, workspaceRoot);
                const verdict = await callCopilot(document.fileName, diff, learned, riskLevel, currentCts.token);

                // Cache the verdict
                verdictCache.set(document.fileName, { hash: diffHash, verdict });

                logVerdict(workspaceRoot, config, document.fileName, verdict);
                updateDiagnostics(diagnosticCollection, document.fileName, verdict);

                if (verdict.flagged && sensitivityAllows(config, verdict.severity)) {
                    statusBar.text = `Q: ● ${verdict.severity}`;
                    statusBar.tooltip = `Q — ${verdict.rule_id}: ${verdict.message}`;
                    await showVerdict(verdict, document.fileName, config, workspaceRoot, context);
                }

                statusBar.text = 'Q: ◦';
                statusBar.tooltip = 'Q Code Conscience — idle';

            } catch (err) {
                if (err.name !== 'Cancelled') {
                    statusBar.text = 'Q: ✕';
                    statusBar.tooltip = `Q error: ${err.message}`;
                } else {
                    statusBar.text = 'Q: ◦';
                }
            }
        }, 1500);
    });
    context.subscriptions.push(saveListener);

    // Clear diagnostics when file is closed
    context.subscriptions.push(
        vscode.workspace.onDidCloseTextDocument(doc => {
            diagnosticCollection.delete(doc.uri);
            verdictCache.delete(doc.fileName);
        })
    );

    // ── Manual review command ───────────────────────────────────────────────
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
                const diff = getFileDiff(editor.document.fileName);
                if (!diff) {
                    vscode.window.showInformationMessage('Q: No diff detected — file may be untracked or unchanged.');
                    statusBar.text = 'Q: ◦';
                    return;
                }

                const riskLevel = classifyDiff(diff);
                if (riskLevel === 'skip') {
                    vscode.window.showInformationMessage('Q: No meaningful code changes detected.');
                    statusBar.text = 'Q: ◦';
                    return;
                }

                if (!checkRateLimit(config)) {
                    vscode.window.showWarningMessage('Q: Rate limit reached. Try again in a moment.');
                    statusBar.text = 'Q: ◦';
                    return;
                }

                const learned = loadLearned(config, workspaceRoot);
                const verdict = await callCopilot(editor.document.fileName, diff, learned, riskLevel, currentCts.token);

                verdictCache.set(editor.document.fileName, { hash: hashString(diff), verdict });
                logVerdict(workspaceRoot, config, editor.document.fileName, verdict);
                updateDiagnostics(diagnosticCollection, editor.document.fileName, verdict);

                if (verdict.flagged) {
                    await showVerdict(verdict, editor.document.fileName, config, workspaceRoot, context);
                } else {
                    await showCleanVerdict(editor.document.fileName);
                }
            } catch (err) {
                vscode.window.showErrorMessage(`Q error: ${err.message}`);
            } finally {
                statusBar.text = 'Q: ◦';
            }
        })
    );

    // ── Open personal exceptions ────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('q.openLearned', async () => {
            const activeFile = vscode.window.activeTextEditor?.document.fileName;
            const workspaceRoot = getWorkspaceRoot(activeFile);
            if (!workspaceRoot) return;
            const config = loadQConfig(workspaceRoot) || DEFAULT_CONFIG;
            const personalPath = path.join(workspaceRoot, config.personal_kb_path || 'knowledge_base/personal/q-learned.md');
            if (fs.existsSync(personalPath)) {
                await vscode.window.showTextDocument(vscode.Uri.file(personalPath));
            } else {
                vscode.window.showInformationMessage('Q: No personal exceptions yet. Make some mistakes first.');
            }
        })
    );

    // ── Open team exceptions ────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand('q.openTeamExceptions', async () => {
            const activeFile = vscode.window.activeTextEditor?.document.fileName;
            const workspaceRoot = getWorkspaceRoot(activeFile);
            if (!workspaceRoot) return;
            const config = loadQConfig(workspaceRoot) || DEFAULT_CONFIG;
            const teamPath = path.join(workspaceRoot, config.team_exceptions_path || 'knowledge_base/team/exceptions/approved.md');
            if (fs.existsSync(teamPath)) {
                await vscode.window.showTextDocument(vscode.Uri.file(teamPath));
            }
        })
    );
}

function deactivate() {}

module.exports = { activate, deactivate };
