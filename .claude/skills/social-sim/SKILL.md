---
name: social-sim
description: Simulate many social media users reacting to a product idea or ad, and keep every persona, reaction and result in a local database. Use when the user wants to test an idea against an audience ("simulate users for a diet app", "como as pessoas reagiriam a esse anúncio", "testar minha ideia nas redes sociais"), create or reuse simulated personas, resume or query a past simulation. By default it researches the market, chooses the audience size itself and simulates each persona in parallel.
---

# social-sim

Simulates an audience of distinct social media users (age, job, income, personality, platforms) seeing an ad for the
user's idea, records each one's reaction, and returns an honest analysis. Personas and results live in a local SQLite
database and are reused across simulations.

## How to run this skill

1. **Read `prompts/orchestrator.md` in this folder first and follow it.** It is the full operating manual: workflow, rules,
   validation, final report format. Then read `prompts/cli_reference.md` (every database command). Read `prompts/persona_generator.md`
   and `prompts/persona_agent.md` when you reach the steps that use them.
2. **Run every database command from the project root** (the directory that contains `bin/socialsim`; from this folder it is
   `../../..`). The only way to touch the database is `bin/socialsim`. Never write SQL or edit the `.db` file directly.
3. The first `bin/socialsim` call creates a local virtualenv and installs dependencies, so it needs network access once.
   If it fails, show the user the error and the suggested command; do not work around it by skipping the database.

## Choose the mode

| The user says... | Mode |
|---|---|
| Gives an idea (and maybe an ad), nothing else | **Autonomous** (default): research, pick segments, decide how many personas, reuse or create them, simulate all, analyze |
| Describes personas to create or names saved ones to use | **Manual**: no research, no audience planning; do exactly what was asked |
| Wants to continue an interrupted or partial run | **Resume**: `run resume`, simulate only the personas it returns |
| Asks about past results | **Query**: use reports and lists; do not simulate |

## Non-negotiable rules

- Open the run (`run start`) before launching persona agents; only the orchestrator writes to the database.
- Simulate each persona in its own subagent, in parallel batches of at most 10, all agents of a batch in one message.
- Do not analyze until every persona agent has returned or been recorded as failed. Never summarize partial results.
- Persona count is 8 to 40 in autonomous mode. Propose it with a one-sentence reason, then ASK the user whether to keep, increase or decrease it, and wait for the answer before creating personas or opening the run. Skip the question only if the user fixed a number or said to run without asking.
- Numbers in the final analysis come from `report run`. Report failures and weak results as plainly as good ones.
- Always close with the caveat: this is a language-model simulation, not market validation; use it to surface objections and hypotheses.
- Answer in the language the user wrote in. Prompts sent to subagents stay in English.

## Files

```
SKILL.md
prompts/
  orchestrator.md       operating manual (read first)
  cli_reference.md      database CLI, exact syntax
  persona_generator.md  template to create personas
  persona_agent.md      template for the per-persona subagent
```
