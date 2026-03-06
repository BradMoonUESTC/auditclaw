You are reviewing one audit task.

Read the assigned task file first: `{{fan_out_file}}`
If `audit-materials/request.md` exists, read it before deciding what to prioritize.

Then:
1. Read the relevant Solidity files and any closely related code paths.
2. Reconstruct the state transitions, trust boundaries, access control rules, accounting logic, and edge cases.
3. Compare intended behavior with actual behavior.
4. Check existing files under `audit-materials/audit/` to avoid duplicate findings.

Derive the task folder name from the parent directory of `{{fan_out_file}}`.
Write your outputs under `audit-materials/audit/<task_folder_name>/`.

Always produce or update:
- `memory.md` with concise notes about what has already been checked
- `summary.md` with what you reviewed and whether issues were found
- `finding.json` in the task folder as the machine-readable source of truth for confirmed issues

If you find concrete issues:
- update `finding.json` immediately instead of waiting until the end
- keep it valid JSON using this shape:
  `{"findings":[{"title":"...","severity":"High|Medium|Low|Info","affected":["file_or_symbol"],"summary":"...","root_cause":"...","impact":"...","remediation":"..."}]}`
- if you also want narrative writeups, you may still add files under `findings/`, but `finding.json` must contain every confirmed issue

Do not stop at generic observations. Confirm the behavior against the code and leave the written artifacts on disk before finishing.
