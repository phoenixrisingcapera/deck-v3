---
source_root: /Users/mpstaton/code/lossless-monorepo/context-v
source_relative_path: agent-skills/splash/src/llms/llms.md
source_repo_slug: lossless-monorepo
collated_at: '2026-08-24'
source_path: "context-v/agent-skills/splash/src/llms/llms.md"
---

# Lossless Agent Skills

> {{SITE_NAME}}

A shared library of [Agent Skills](https://agentskills.io/specification) used by Lossless Group team members and AI coding agents on Lossless projects. Skills here are tool-agnostic: they work with [pi-coding-agent](https://github.com/badlogic/pi-mono), Claude Code, OpenAI Codex, and anything else that follows the Agent Skills spec.

This site is the collection's GitHub Pages splash. It surfaces {{SKILL_COUNT}} skills and {{CHANGELOG_COUNT}} changelog entries authored alongside the collection. The companion `/llms-full.txt` concatenates the raw markdown of every skill and changelog entry for one-fetch LLM ingest.

## Reference

- [Full-text search]({{SEARCH_URL}}): Pagefind-indexed across every skill body and changelog entry.
- [Full corpus content]({{LLMS_FULL_URL}}): every skill and changelog entry concatenated as raw markdown — preferred ingest target for LLMs that can handle a single large document.
- [Source repository](https://github.com/lossless-group/lossless-agent-skills): the skills, the splash, the changelog.
- [Lossless Group](https://lossless.group): the org that maintains this practice.

## Skills

The full catalog. Tool-agnostic skills meant to be loaded by any Agent-Skills-spec-conforming runtime. Alphabetical by title.

{{SKILLS_INDEX}}

## Changelog

Entry-by-entry release notes for the collection, sorted by `date_modified` descending. Following the Lossless Group changelog conventions.

{{CHANGELOG_INDEX}}
