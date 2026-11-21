# UPS helper guidance

This repository owns UPS observation, policy simulation and its documented
operating procedures. Read the README and relevant project documentation for
the current branch before acting. Recorded hardware observations are snapshots.
Check current state before operating equipment, and follow the owner's
authorization for any power, shutdown, maintenance or network control.

## Homelab instruction tree

When checked out at `projects/UPS-helper` in the homelab monorepo, read
[the parent guidance](../../AGENTS.md) and use its project index to find sibling
guidance relevant to the task. In a standalone checkout, read the
[homelab guidance on development](https://github.com/georgeasiminei/homelab-monorepo/blob/development/AGENTS.md)
and locate sibling repositories through its project index. Apply the instructions
for the repository and branch being changed.

When modifying any AGENTS.md, review its parent, relevant children and siblings
for affected links, ownership and instructions. Update affected guidance in its
own repository through its branch workflow. After a change reaches UPS staging,
update the monorepo's pinned commit through its own PR. Keep instructions
authoritative in their owning file and links current as projects are added,
removed or renamed.

## Git and validation

Fetch before creating a feature branch from the latest `origin/development`.
Validate, commit, push and open a PR to `development`. Use a separate branch
from `origin/staging` for changes intended for staging when development contains
unrelated work. Preserve the established content of each branch. Validate changes
at the affected project boundary and report what was checked.
