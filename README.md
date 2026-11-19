# app-test-architecture-lite

English | [繁體中文](README.zh-TW.md)

A free Claude Code skill that has the AI build a mobile app UI test-automation architecture for your company from scratch, using **Maestro**. It follows one flow: **interview → decide → propose → roll out in phases → verify**.

The AI first asks you 12 questions: current state, platforms, development process, main flow, test data, devices, secrets rules and reporting. It then picks the core modules from a decision table and shows you a proposal. Nothing is created until you approve it. The result is an architecture that runs reliably every day and produces failure reports people can read.

It comes from a production Maestro project that runs daily regression (all identifying details removed).

> The skill content (`SKILL.md`, `references/`, `templates/`) is written in Traditional Chinese. The AI will still answer in your language.

---

## What's included

- **Process and rules**: interview pipeline, decision table, quick mode, pre-delivery self-check
- **Core modules**:
  - M1 single entry runner (watchdog, device lock, report, exit code)
  - M2 layered config
  - M3 externalized locators
  - M4 data-driven loops
  - M5 shared subflows
  - M6 popup and wait resilience
  - M7 basic back-office API hooks
  - M9 result judgement and single-file HTML report
  - M11 re-run failed / flaky marking
  - M12 element inspection tool
  - M13 knowledge layer
  - M14 VCS rules
  - M15 GitHub Actions
- **Ready-to-use templates**: `run_suite.sh`, popup helpers, report and judgement scripts, `snap.sh`, notifications (Slack-style / Teams / LINE / email), GitHub Actions, config samples
- **A Maestro pitfalls list** from real runs, and a worked example with identifying details removed

## Installation

Copy the whole folder: `SKILL.md` references files in `references/` and `templates/`.

```bash
# available in every project
cp -R app-test-architecture-lite ~/.claude/skills/
# or for one repo only
cp -R app-test-architecture-lite <repo>/.claude/skills/
```

Start a new Claude Code session afterwards.

## Usage

```
/app-test-architecture-lite We want to introduce app test automation with Maestro. Please plan it.
```

You can also just describe the need ("set up app test automation for our company") and the AI loads the skill from its description.
If you're short on time, say "give me a minimal runnable skeleton first". The AI asks only 4 questions and produces an MVP.

## Requirements

- Maestro CLI, a JDK, the Android SDK (iOS needs macOS + Xcode)
- Python 3.9+ (`pip install -r templates/requirements.txt`)
- A macOS or Linux runner; on Windows use WSL2

## Lite vs. full version

<!-- Before publishing, replace <FULL_VERSION_URL> on the next line with the link to the full version (Agensi) -->
**Full version**(Coming Soon): [app-test-architecture-builder](<FULL_VERSION_URL>)

| | Lite (free) | Full version |
|---|---|---|
| Test tools | Maestro only | Maestro, Appium (Java / Python / TypeScript), XCUITest + Espresso / Compose tests, Detox, Playwright, with setup guides for each |
| Tool selection | Fixed to Maestro | Picks a tool from app tech, who maintains tests, device source and macOS availability; includes a device-farm × tool compatibility table |
| Devices | Local emulators/simulators, USB devices | Also cloud device farms (BrowserStack, Sauce, AWS Device Farm, Firebase Test Lab, Maestro Cloud) |
| Interview | 12 questions | About 30 questions, with follow-ups and branching |
| Quick mode | 1 round, 4 questions | 2 rounds, 7 questions |
| Existing frameworks | Absorbing loose scripts | Framework scoring, run-old-and-new-side-by-side rework path with measurable definitions of done |
| Modules | 13 core modules | 20: adds mocking, visual regression, test-case-system upload, audit evidence, device pools, accessibility, trend reports |
| Capability catalog | 8 common out-of-app steps (OTP, verification email, back-office approval, payment, upload, permissions, push, location) | 32: also enterprise SSO, TOTP, biometrics, IoT / Bluetooth, in-app purchases, game canvases, media playback, video calls, interacting apps, feature flags, tablets, MDM / kiosk, hardware scanners, App Clips, system wallets, OTA and more |
| Dimensions | Basic brand and environment handling | Also multi-tenant, multi-locale, feature-flag combinations, tablets, shared white-label locators and brand-matrix sampling |
| Compliance | Secrets kept out of VCS, basic no-egress settings | Report and log masking, evidence retention (SHA-256 manifest), signed PDF evidence reports, data residency, Vault |
| CI templates | GitHub Actions | GitHub Actions, GitLab, Jenkins, Azure Pipelines, Bitbucket |
| Other templates | Runner, re-run, popup helpers, judgement and report, `snap.sh`, notifications, config samples | Also visual regression, trend report, TestRail upload, evidence archiving, device health check |
| Pitfall lists | Maestro | Maestro + Appium |
| Worked example | First part of the case (layout, config, locators, loops, helpers, API hooks) | Full case, including report internals and visual regression |
| Validation | Independent audit with a new sample confirmed it works standalone | 10 rounds of simulated audits across different industries |

Both versions share the same flow (interview → decide → propose → roll out in phases → verify) and core rules, the same design principles for the core modules, and the same code for the core templates (runner, judgement, report, re-run, popup helpers).

When Lite meets a need outside its scope, it says so plainly and lists it under "later / out of scope" in the proposal, rather than pretending the Lite templates can do it.

## Limitations

- The templates pass syntax checks and were exercised with simulated data. **They have not yet been run end to end on real devices.** On first adoption the AI verifies them in phase 0 with a hello-world flow.
- Maestro behaviour can change between versions. Verify against real runs (see `references/maestro-pitfalls.md`).

## License

MIT. See [LICENSE](LICENSE).
