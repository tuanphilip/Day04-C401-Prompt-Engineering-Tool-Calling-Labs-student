---
name: source_audit
track: custom
kind: local_formatter
requires_env: []
inputs: [markdown, items, min_sources]
outputs: [status, source_count, missing_url_count, warnings, checklist]
side_effect: false
---
# source_audit

Checks whether a research draft or item list has enough source evidence before
publication. It looks for URLs, missing item URLs, weak source labels, and
basic pre-publish citation readiness. It does not fetch new sources.
