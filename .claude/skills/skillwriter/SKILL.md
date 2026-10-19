---
name: skillwriter
description: Write a new project skill when a task in KI-Projekt recurs (same scripts, commands or checks done a second time, or "again", "every matchday", "after each backtest"), or when Nikita asks for a skill. Proposes the skill first, then writes it in the house style of .claude/skills and .claude/agents.
---

# Skillwriter

Turns a recurring task into a skill in `.claude/skills/<name>/SKILL.md` that behaves like the existing skills and agents: sober, evidence-based, median across runs, per-outcome H/D/A, uncertainty stated, no secrets.

## When to Use

- The same sequence of scripts, commands or checks is being done a **second** time (in this session, in git history, or Nikita says it is regular).
- Nikita describes a routine ("before every matchday I …", "after each backtest I …").
- Nikita asks for a new skill.

## When NOT to Use

- One-off work (a migration, a single patch script such as `patch_add_future_vs_reference_metrics.py`).
- An existing skill already covers it. Extend that skill instead (see Step 2).
- Exploratory analysis whose steps are not settled yet. Wait until it has been done the same way twice.
- Roles rather than tasks (planning, debugging, performance, security): those are agents in `.claude/agents/`.

## Workflow

### Step 1: Capture the recurrence

```markdown
- Task in one sentence:
- Evidence it recurs: [this session twice / git log / Nikita's words]
- Exact commands and scripts used (with paths):
- Inputs, outputs, env vars or modes involved:
- Cost: runtime, API quota, files overwritten
```
No evidence of recurrence → do not write a skill; say so in one line.

### Step 2: Check for overlap

```bash
ls .claude/skills
grep -h "^description:" .claude/skills/*/SKILL.md
```
Compare against `.claude/skills/README.md`. If an existing skill covers more than half of the task, propose an edit to that skill instead of a new one.

### Step 3: Read the scripts, not just their names

- Docstring, `argparse` options, env vars, output paths (`grep -nE "add_argument|os.environ|to_csv" script.py`).
- Note anything destructive (files overwritten, folders skipped, quota used).
- `AI_match_stats_prediction.py` is ~3,700 lines: Grep and line ranges only.

### Step 4: Propose, then wait

Nikita works plan-first. Post the proposal and do not write files until it is approved:

```text
Proposed skill: <kebab-case-name>
Why: <evidence it recurs>
Wraps: <scripts / commands>
Invocation: auto | manual only (reason)
Writes: <files or folders it changes>
Overlap: none | extends <skill>
Questions: <only if the answer changes the skill>, one line per option, recommendation marked
```

### Step 5: Write it in the house style

Use `TEMPLATE.md` in this folder. Rules:

| Rule | Why |
|---|---|
| `name` in kebab-case, verb-noun (`run-backtest`, `diagnose-draws`) | Matches existing skills |
| `description`: what it does + when to use it, one or two sentences, with trigger words Nikita would actually type | Claude picks skills by description |
| `disable-model-invocation: true` if it runs BART, takes > ~10 min, uses API quota, overwrites data, or uploads anything | Same rule as `run-backtest` and `collect-matchday-data` |
| Interpreter `PY="C:/AI Projekt/.venv/Scripts/python.exe"`, quoted paths with spaces | Same as all other skills |
| Wrap existing scripts. A new script only if nothing exists; then put it in the skill folder, resolve paths from `Path(__file__)`, and test it before reporting | `calibration-report` pattern |
| "How to Read It" section with the statistical caveats that apply (median across runs, never best run; 9 matches per matchday; per-outcome guardrail; in-sample vs. leave-one-matchday-out) | Same evaluation standard as `CLAUDE.md` |
| Fixed "Output Format" block | Every skill reports the same way |
| Never print API keys or SFTP credentials; reference config files by path | Same as `security` agent |
| English, sober, no filler; under ~80 lines | Same as existing skills |

### Step 6: Register and verify

1. Add a row to `.claude/skills/README.md` (skill, invocation, wraps).
2. Check the frontmatter parses: starts with `---`, has `name` and `description`, closes with `---`.
3. Dry-run the cheapest command in the skill (`--help`, `--dry-run`, `py_compile`) and report the result.
4. Do not commit unless asked.

## Output Format

```text
Skill written: .claude/skills/<name>/SKILL.md  (invocation: auto | manual)
Wraps: <scripts>
README updated: yes
Verified: <command> → <result>
Not verified: <what and why>
```

**Remember:** a skill is earned by repetition. Propose first, write second, verify third.
