# Vendored Agent Skills

This directory vendors the upstream `addyosmani/agent-skills` project for local, repository-scoped use.

## Source

- Repository: `https://github.com/addyosmani/agent-skills`
- Commit: `9534f44c5448086fcc0046f9d83752c654c81930`
- License: see [agent-skills.LICENSE](/d:/University/Assignments/agile-assignment/.agents/agent-skills.LICENSE)

## Layout

```text
.agents/
  agents/       Upstream persona files
  references/   Shared reference documents
  skills/       Imported skill folders
```

## Notes

- The upstream skill content was copied into this repo rather than added as a submodule.
- Shared reference files are available both in `.agents/references` and under each skill's local `references/` folder so relative references inside upstream `SKILL.md` files keep working without editing upstream skill content.
