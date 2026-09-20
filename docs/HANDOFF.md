# Current handoff

Prepared: **2026-09-21**; Git, CI and test evidence below was checked on
**2026-09-20**, unless noted otherwise. Read [AGENTS.md](../AGENTS.md) first, then
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) and [DECISIONS.md](DECISIONS.md).
This is a resumable working-state summary, not the full conversation archive.

## Current request and scope

The user first requested four context files, then explicitly requested a PR for
**all pending source, test and documentation changes** on 2026-09-21. The existing
PR #1 remains OPEN and is used for the combined change set: HW firmware, ASUS
shared Day/Night migration, tests/CI and these four context files. No duplicate
PR is needed for the same branch. Merge, deployment, restart and firmware flashing
are not part of this request. Check GitHub for current remote publication/CI state.

## Git and PR: VERIFIED 2026-09-20

- Work from `C:\Work\SmartHomeServer\SmartHomeHA`, a separate repository from its
  parent. Origin: `https://github.com/OrestHudyma/SmartHomeHA.git`.
- Branch: `feature/hw-interface-firmware`.
- HEAD: `c63b38d9971438d53f1e3af1aaf3eddd078e7a68`:
  **Fix HW packet handling and add firmware regression tests**.
- Previous commit: `e0464c2`, initial HW project import.
- [PR #1](https://github.com/OrestHudyma/SmartHomeHA/pull/1) is **OPEN**, base `main`,
  remote head matches local HEAD; not merged. Queried using GitHub CLI.
- Local ancestor `1fb73f6` is the Bridge 0.1.3 Alarm commit; do not assume it is
  still the current remote main without checking.
- GitHub PR checks all pass: bridge tests, HW host-tests, amd64 and arm64 container
  builds. Example runs: [bridge/container CI](https://github.com/OrestHudyma/SmartHomeHA/actions/runs/34957108818),
  [HW CI](https://github.com/OrestHudyma/SmartHomeHA/actions/runs/34957108805).
  These results concern committed code, not the uncommitted migration below.

Optional local helper: `.tools/github.ps1` wraps the installed GitHub CLI using
Git's stored credential. Never print the credential. On this machine it was run
with process-local `powershell -NoProfile -ExecutionPolicy Bypass -File
.\.tools\github.ps1 ...`; no global execution-policy change is needed.

## Pending changes included in the combined PR change set

These existed **before** the documentation task and are now included at the user's
request (the status below records their pre-commit state):

```text
 M .github/workflows/ci.yaml
 M extras/README.md
 D extras/asus-brightness/asus_display.yaml
?? extras/asus-brightness/day_night.yaml
?? extras/asus-brightness/day_night_automations.yaml
?? extras/asus-brightness/day_night_card.yaml
?? extras/asus-brightness/test_day_night.py
```

These implement/document the shared Day/Night package and UI-editable automation
split. The CI diff expands the ASUS test pattern from `test_brightness.py` to
`test_*.py`. They are committed with the documentation after the earlier HW commits.

Also untracked: `SmartHome_HW/HW_interface.cydsn/Export/`, `Generated_Source/`,
`HW_interface.cycdx`, `.cyfit`, `.cyprj.Orest`, `.rpt`, `.svd`, and
`SmartHome_HW/SmartHome_HW.cywrk.Orest`. Generated/personal artifacts are not tracked
and are not all ignored by Git. Preserve them; do not delete them or use `git add .`.

The four context files are also included. Generated/personal artifacts above stay
untracked and outside the PR. Refresh Git status before any future staging operation.

## Verification run for this snapshot

**VERIFIED again 2026-09-21**, local Python 3.11 and GCC; no live hardware or household
MQTT connection. Commands are in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md#verification).

| Check | Result |
| --- | --- |
| Upstream byte integrity | Both Python files match recorded hashes and upstream Git blobs |
| Bridge test suite | 65 discovered: 60 passed, 5 integration tests skipped |
| ASUS suite (`test_*.py`) | 13 passed, including the shared-mode configuration tests |
| HW native host regression suite | 14 passed |
| Earlier PR CI (2026-09-20) | All reported checks passed for the HW head; new pushes need fresh checks |

The local run did not start a broker, perform Linux PTY integration, rebuild
containers, build with PSoC Creator or flash/test a controller. ASUS YAML contract
tests do not replace HA configuration validation or physical brightness testing.

## HW firmware status

**VERIFIED in source/README:** the PR imports the PSoC Creator project and fixes
RX bounds, checksum handling, field parsing, fixed header/command matching,
resynchronization, invalid-character checks and pending RF output-buffer ownership.
Tests include real `main.c` and mock PSoC APIs, including interrupted transmission
and main-loop ACK scenarios. See [HW README](../SmartHome_HW/README.md).

Remaining documented limitations, not resolved by passing tests:

- Busy radio packets are discarded.
- Overflow does not discard input until a fresh start delimiter.
- Local-command buffers are not protected against concurrent replacement.
- Invalid local packets still share the radio-forwarding path.
- Host tests do not validate target compiler/code generation, UART timing,
  interrupt priorities or actual RF reception.

No completed target build/flash or physical acceptance is established by this
handoff. Do not describe the firmware as fully validated on hardware.

## Live HA status and open follow-ups

No SSH connection or live HA configuration inspection was performed for this
documentation task. Historical versions/access locations are in PROJECT_CONTEXT.

1. **Grow light automations:** latest screenshots match the agreed schedule and
   presence/illuminance design in DECISIONS. Last screenshot showed a Save button;
   saving and runtime behavior are not confirmed. Actual entity IDs, exported YAML,
   bridge-start recovery and sensor availability need inspection if troubleshooting.
2. **ASUS shared Day/Night:** migration and its 13 passing tests are included in
   the combined PR change set. Current remote installation parity is not freshly
   verified; publishing these files does not install them on HA or ASUS.
3. **Zigbee:** dongle connected per user; Zigbee2MQTT is only a recommendation so
   far. Do not install/flash/pair solely on the basis of this file.
4. **Bridge crash investigation:** user previously reported a crash and enabled
   autostart/watchdog. No verified root cause is preserved here; do not invent one
   or assume watchdog fixed the cause.
5. **Release metadata mismatch, VERIFIED in source 2026-09-21:**
   `smarthome_bridge/config.yaml` and `app/discovery.py` say 0.1.3, but
   `smarthome_bridge/Dockerfile` defaults `BUILD_VERSION` to 0.1.2. Record for the
   next release review; no code fix or runtime impact assessment was performed.
6. **Other parked topics:** Samsung TV energy readings at zero (explicitly deferred),
   apartment floorplan dashboard, strict dashboard-only access, remote-access
   options, Ajax capabilities and Samsung Now Brief. These are not current tasks
   and are not recorded as implemented integrations.

## Starting the next chat

Suggested message (replace the task, not the context files):

> Read AGENTS.md, docs/PROJECT_CONTEXT.md, docs/DECISIONS.md and docs/HANDOFF.md in
> C:\Work\SmartHomeServer\SmartHomeHA. Check the branch and git status, preserve
> unrelated work, and continue with: [specific task]. Reply in Ukrainian.

After the next meaningful milestone, update this file's date, branch/PR state,
verification evidence and next steps. Keep stable architecture in PROJECT_CONTEXT
and accepted behavior in DECISIONS; do not append a transcript or copy secrets.
