# Agents

Project subagents, modelled on the ECC agent format (frontmatter + role, workflow, project-specific checks, output format, when not to use).

| Agent | Model | Edits? | Use for |
|---|---|---|---|
| `planner` | opus | no (`permissionMode: plan`, read-only tools) | Any plan; used automatically in plan mode |
| `debugger` | opus | yes, minimal fixes | Failing runs, wrong-looking results |
| `efficiency` | sonnet | yes, measured and result-preserving | Slow runs, memory, API quota |
| `security` | sonnet | no, report only | Secrets, git exposure, dependencies, Hostinger deployment |
