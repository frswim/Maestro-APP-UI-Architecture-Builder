# app-test-architecture-builder

English | [繁體中文](README.zh-TW.md)

A Claude Code skill that has the AI build or rework a mobile app (Android / iOS / cross-platform / hybrid) UI test-automation architecture for a company in any industry. It follows one flow: **interview → decide → propose → roll out in phases → verify**.

The architecture is modular. The AI first interviews you about your current state, development process, platforms, test scope, infrastructure and reporting needs. It then decides which modules to add and which to leave out, rather than forcing one fixed setup onto every company.

It comes from a production Maestro project that runs daily regression across multiple brands (all identifying details removed). It was then refined through 10 rounds of simulated audits, each using a company from a different industry.

> The skill content itself (`SKILL.md`, `references/`, `templates/`) is written in Traditional Chinese. The AI will still answer in the user's language.

---

## When to use it

- "Help us set up mobile app test automation for our company."
- "We already have automation (Maestro / Appium / XCUITest…) but it's flaky. Please assess and improve it."
- "Port this test architecture to a new product or project."
- "We want to start UI automation. Where do we begin?"

**Not for**: fixing a single flow or a single locator in an existing, settled project. Use that project's own skills for that.

---

## Installation

A skill is a folder. **Copy the whole folder**: `SKILL.md` references files in `references/` and `templates/`.

| Use | Location |
|---|---|
| One repo only (can be committed and shared with the team) | `<repo>/.claude/skills/app-test-architecture-builder/` |
| All projects (personal) | `~/.claude/skills/app-test-architecture-builder/` |

```bash
cp -R <source>/app-test-architecture-builder ~/.claude/skills/
```

Start a new Claude Code session after copying.

---

## Usage

### 1. Slash command (most reliable)

```
/app-test-architecture-builder We want to introduce app test automation. Please plan it.
```

### 2. Just describe the need

Say something like "set up app test automation for our company" or "assess our existing automation framework". The AI loads the skill based on its description. That's the AI's own judgment, so use the slash command if you need to be sure.

### 3. Quick mode

If you're short on time, say "give me a minimal runnable skeleton first". The AI asks only 2 rounds, 7 questions in total:
- current automation
- platform
- whether several apps interact
- who maintains the tests
- device source
- runner OS
- the first main flow, including any steps outside the app

Everything else uses defaults to produce an MVP. The defaults are listed as "assumptions to confirm" and revisited later.

### Good to have ready

- Repo path, if you have one. The AI scans it first and won't ask what it can infer.
- Test-case spec (Excel / TestRail / Jira, etc.).
- The first main flow you want automated, from opening the app to the end.
- Basics about test accounts, devices and CI.

---

## Pipeline

```
P0   Kickoff & scan (read the repo first; don't ask what can be inferred)
P1   Current automation → new build / incremental rework / run old and new side by side
P2   Product & platform (app type, multi-brand/tenant, interacting apps, locales, environments, feature flags)
P3   Development process (cadence, CI/CD, test-case management, who maintains, VCS rules)
P4   Scope & data (main flow, test data, out-of-app steps, special-capability checklist)
P5   Infrastructure & constraints (devices, runners, compliance, timeline, staffing)
P5.5 Tool selection (app tech × who writes × device source × macOS available; recorded as an ADR)
P6   Reporting & gates (audience, gating rules, visual regression, trends, formal evidence documents)
P7   Decide (answers → module list)
P8   Proposal → nothing is created until you approve
P9   Phased rollout (MVP → expansion), with a checklist per phase
P10  Handover (user manual, maintainer guide, design docs, release notes)
```

Each round asks at most 4 multiple-choice questions. After each round the AI reports what it now knows, which modules that implies, and what it will ask next. Answers are collected in `docs/test-architecture/intake.md` and shown to you before the proposal.

---

## Modules (M1–M20)

| Module | What it covers | Default |
|---|---|---|
| M1 | Single entry runner (config loading, resource switching, output dir, watchdog, report, exit code; cloud-farm mode) | Always |
| M2 | Layered config (brand / environment / secrets / test data kept apart; Vault, multi-tenant, locales) | Always |
| M3 | Externalized locators (per platform / brand, `active` switch, `_base` + brand overrides) | Always |
| M4 | Data-driven loops (account × case, dispatch by type to variant subflows) | Conditional |
| M5 | Shared subflows (login, navigation, cleanup) | Always |
| M6 | Resilience (wait-for-anchor + dismiss-popup helper, bounded retries, `TIMEOUT_SCALE`) | Usually |
| M7 | Back-office / API hooks (approvals, OTP, data setup, counterpart-role bots) | Conditional |
| M8 | Mocking (proxy response overrides, poor network) | Conditional |
| M9 | Result judgement + human-readable report (PASS / FAIL / BLOCKED / flaky, masking, i18n, single-file HTML) | Always |
| M10 | Visual regression (separate capture and check modes, ignore regions) | Conditional |
| M11 | Re-run failed only, flaky marking | Recommended |
| M12 | Dev & environment tools (setup script, element inspection, test-file push) | Always |
| M13 | Knowledge layer (user manual, maintainer guide, subsystem design docs, release notes) | Always |
| M14 | Collaboration & VCS (`.gitignore`, offline bundle exchange) | Always |
| M15 | CI integration (GitHub Actions / GitLab / Jenkins / Azure / Bitbucket) | Conditional |
| M16 | Spec import & traceability (Excel / TestRail / Xray / Zephyr / Azure Test Plans) | Conditional |
| M17 | Audit evidence (masking, SHA-256 manifest, retention, signed PDF evidence report) | Conditional |
| M18 | Device pool & parallel runs (device locks, health checks, hardware pool, brand-matrix sampling) | Conditional |
| M19 | Automated accessibility checks (WCAG) | Conditional |
| M20 | Result history & trends (weekly pass rate, most failed / flaky) | Conditional |

[references/decision-matrix.md](references/decision-matrix.md) shows which answer pulls in which module.

---

## Supported tools and environments

- **Test tools**: Maestro (most complete templates), Appium (Java / Python / TypeScript), native XCUITest + Espresso / Compose UI tests, Detox, Playwright (for the web layer of hybrid apps). See [references/tool-adaptation.md](references/tool-adaptation.md) for how to set up the modules with tools other than Maestro.
- **App tech**: native Android / iOS, React Native, Flutter, Kotlin Multiplatform, hybrid (Ionic / Capacitor, etc.), and embedded canvas UIs such as Unity.
- **Device sources**: local emulators/simulators, an in-house device lab, BrowserStack / Sauce Labs / AWS Device Farm / Firebase Test Lab / Maestro Cloud. A table shows which device farms support which tools.
- **Special capabilities**: 32 of them, each with ranked approaches and platform limits, e.g. OTP, TOTP, enterprise SSO, biometrics, push notifications, payment sandboxes, in-app purchases, camera / barcode scanning, hardware scanners, Bluetooth / IoT, poor network and offline sync, video calls, interacting apps, feature flags, tablets, MDM, App Clips. See [references/capability-catalog.md](references/capability-catalog.md).

If a combination isn't covered, or is marked "needs verification", the AI lists it as a pending spike. It proves it with a hello-world test in the real environment before putting it in the proposal.

---

## Layout

```
app-test-architecture-builder/
├── SKILL.md                     # Entry point: core rules, pipeline, self-check, file index
├── references/
│   ├── interview-pipeline.md    # P0–P6 questions, follow-ups, impact on design, P5.5 tool selection
│   ├── decision-matrix.md       # Answers → modules, defaults, conflict handling
│   ├── architecture-modules.md  # M1–M20 specs and cross-tool mapping
│   ├── capability-catalog.md    # 32 special capabilities and how to handle them
│   ├── tool-adaptation.md       # Appium / pytest / WDIO / native framework setup, result JSON schema
│   ├── maestro-pitfalls.md      # Maestro behaviour and pitfalls found in real runs
│   ├── appium-pitfalls.md       # Appium pitfalls
│   ├── rollout-plan.md          # Phased plans for new builds and reworks, definitions of done
│   ├── reference-implementation.md  # The original project (identifying details removed)
│   ├── sanitization-checklist.md    # Checklist for stripping sensitive details
│   └── audit-history.md         # Issues found and fixed across 10 simulated audits
└── templates/                   # Ready-to-copy templates
    ├── run_suite.sh / run_failed.sh               # M1 runner, M11 re-run
    ├── wait_anchor_or_dismiss.yaml and 3 others   # M6 Maestro resilience helpers
    ├── failure_rules.py / generate_report.py / _summarize_results.py / flow_index.py   # M9 judgement & report
    ├── ui_diff_check.py / ui_diff_define_ignore.py / ui_diff_checkpoint.yaml           # M10 visual regression
    ├── trend_report.py                            # M20 trends
    ├── archive_evidence.sh / device_health_check.sh   # M17 evidence, M18 device health
    ├── notify.sh / notify_payload.py              # Notifications (Slack-style / Teams / LINE / email)
    ├── push_testrail.py                           # TestRail result upload
    ├── ci-github-actions.yml / ci-gitlab.yml / Jenkinsfile / azure-pipelines.yml / bitbucket-pipelines.yml
    ├── config-examples.md                         # Brand config, locators, test data, masking, .gitignore samples
    ├── intake-summary.md / architecture-decision-record.md
    └── requirements.txt
```

---

## Notes on the templates

- The `*.yaml` helpers are Maestro-only, and `run_suite.sh` is Maestro local mode. With another tool, the runner, wait helper and result format must be rewritten for that tool. The report layout, masking, i18n, visual diff, notifications and trends still work as long as your tests write `*.result.json` files (schema in `tool-adaptation.md` §3.1).
- The Python scripts need Python 3.9+. Dependencies are in `templates/requirements.txt`.
- `run_suite.sh` switches targets via environment variables, mainly `TARGET_ENV`, `PLATFORM`, `LOCALE`, `FLAGS`, `FORM_FACTOR`, `DEVICE`, `DEVICE_MODEL` and `TIMEOUT_SCALE`. The script header lists them all.
- On Windows, use WSL2. Git Bash has no `pkill`, so the watchdog won't work there.
- The templates share naming conventions: locator paths, loop variable names, helper file names and status-file keys. Rename them together. See section 7 of `SKILL.md`.

---

## Limitations

- The templates pass syntax checks and were exercised with simulated Maestro output and synthetic data. **They have not yet been run end to end on real devices.** On first adoption the AI verifies them in phase 0 with a hello-world test.
- The compatibility tables (farm support, tool commands, platform limits) will go stale as tools change. Verify against the real environment.
- Hardware itself (firmware, electrical), voice commands and extended surfaces such as wearables are out of scope. The proposal lists them explicitly as excluded or manual.

---

## Maintenance

- Before editing, read [references/audit-history.md](references/audit-history.md) so you don't reintroduce issues that were already fixed.
- Before adding examples or templates, strip sensitive details using [references/sanitization-checklist.md](references/sanitization-checklist.md). Keep any project-specific keyword list out of the skill.
- After changes, run one simulated audit with a new fictional company and record it in the same format as `audit-history.md`.
