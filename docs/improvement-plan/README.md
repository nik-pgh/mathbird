# Improvement plan

Tracked work from the codebase review. GitHub issues:

| Phase | Issue | Title |
| --- | --- | --- |
| 0 | [#28](https://github.com/nik-pgh/mathbird/issues/28) | Documentation truth sync |
| 1a | [#29](https://github.com/nik-pgh/mathbird/issues/29) | Security: document ownership & ACL |
| 1b | [#30](https://github.com/nik-pgh/mathbird/issues/30) | Security: cookies, upload limits, eval gate |
| 2a | [#31](https://github.com/nik-pgh/mathbird/issues/31) | Async I/O: storage utils & UserStore pooling |
| 2b | [#32](https://github.com/nik-pgh/mathbird/issues/32) | Background ingest jobs |
| 3 | [#33](https://github.com/nik-pgh/mathbird/issues/33) | Frontend performance: bundle split & render |
| 4 | [#34](https://github.com/nik-pgh/mathbird/issues/34) | Code health: dedup & dead code removal |
| 5 | [#35](https://github.com/nik-pgh/mathbird/issues/35) | Progress & RAG efficiency |
| 6 | [#36](https://github.com/nik-pgh/mathbird/issues/36) | Product polish: logout, errors, eval UX |

Re-create issues (if needed):

```bash
./scripts/create_improvement_issues.sh
```

Issue bodies live in `docs/improvement-plan/issues/`.
