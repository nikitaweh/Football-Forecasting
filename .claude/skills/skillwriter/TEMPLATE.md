---
name: <verb-noun>
description: <What it does in one sentence>. Use <when / trigger words>.
# disable-model-invocation: true   # uncomment if: BART runs, > ~10 min, API quota, overwrites data, uploads
---

# <Title>

<One short paragraph: what the scripts do, what they read and write, whether it is read-only or post-hoc.>

## When to Use

- <situation>
- <situation>

Not for <neighbouring task>: use `<other-skill>`.

## Before Running            <!-- only if something is destructive or costly -->

1. <backup / confirmation / quota check>

## Run

```bash
PY="C:/AI Projekt/.venv/Scripts/python.exe"
cd "Sports Api Data/Testruns/Code"
"$PY" <script>.py <args>
```

## How to Read It

- <metric definition and the deployable forecast used>
- <statistical caveat: median across runs, sample size, guardrail, in-sample vs LOMO>

## Output Format

```text
<fixed report block with the numbers that matter and their uncertainty>
```
