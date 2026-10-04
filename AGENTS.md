# Working agreements

This is the **SmartHomeHA** repository, nested inside a separate
`C:\Work\SmartHomeServer` checkout. Run Git commands from this repository, not its
parent. See HANDOFF for the dated Git-state inventory.

## Resume a session

Read [project context](docs/PROJECT_CONTEXT.md), [decisions](docs/DECISIONS.md),
and [handoff](docs/HANDOFF.md). Then inspect `git status --short`, the current
branch and relevant diffs. These documents are dated evidence, not proof of the
current server state; code and fresh observations take precedence.

## Communication and authorization

- Speak Ukrainian with the user. Use English for repository documentation, code
  comments and Home Assistant display names. Preserve existing entity IDs unless
  migration is requested: older IDs may be transliterated Ukrainian.
- For code findings/proposals, give clickable file links with current line numbers.
- Prefer named constants to unexplained numbers in new code.
- Review/diagnosis requests do not authorize fixes. Implement edits when requested;
  a request to propose changes means proposals only.
- Preserve unrelated changes and unsaved editor buffers. Do not reset, overwrite,
  clean, stage or commit them indiscriminately. Use explicit file lists for commits.
- Do not claim an editor preview/Keep workflow if the current tools do not provide
  one. Avoid disk edits that conflict with unsaved work; ask when this cannot be
  resolved safely.
- Creating a commit, pushing/merging a PR, deploying, restarting services, flashing
  firmware or physically switching devices must fit the current authorization.
  Previous deployment permission is not a standing instruction to deploy every edit.
- Read-only SSH diagnostics on the user's servers were requested as the preferred
  way to verify deployment issues. Do not print credentials or include them in Git.

## Implementation boundaries

- Keep `app/periphery.py` and `app/nmea.py` under `smarthome_bridge/` byte-identical
  to the pinned **SmartHomeServer Python source**, not to MCU firmware. Prefer
  adapters/subclasses. Improvements may be proposed; changing the pinned files
  requires an explicitly agreed update of the upstream contract and tests.
- Never treat a serial ACK or a displayed power state as RF/relay confirmation.
- Only one process may own each physical serial port. Distinguish the 433 MHz
  controller from the Zigbee dongle; prefer stable `/dev/serial/by-id/` paths.
- UI-editable HA automations belong in `automations.yaml` with stable unique IDs.
  Merge entries; do not replace unrelated automations or edit `.storage` directly.
- Keep secrets, real options/state files, browser sessions and generated/personal
  PSoC artifacts out of commits. Untracked does not mean disposable.

## Verification and handoff

Use [DEVELOPMENT.md](DEVELOPMENT.md) and [the test commands](docs/PROJECT_CONTEXT.md#verification).
Distinguish unit/host tests, integration tests, target builds and physical tests.
Report skips and limitations, not just a green summary. Update the dated handoff
after a meaningful milestone and decisions only when an agreement changes.
No automatic commits or deployments are implied by these rules.
