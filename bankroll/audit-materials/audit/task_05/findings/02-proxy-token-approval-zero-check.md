Title: Proxy does not reset approvals and may assume ERC20 semantics

Severity: Low

Affected files/functions:
- `proxy_wbnb.sol` — `buyFor`, `donatePool`

Description / root cause
- The proxy uses `token.approve(stackAddress, _balance)` without first setting allowance to zero. Some ERC20 implementations require setting allowance to zero before changing it to a new value to mitigate the race condition in `approve`.
- The proxy does not check return values beyond `transferFrom` (it does check approve return implicitly by relying on standard ERC20), but untrusted tokens may return false or revert.

Impact / exploit scenario
- With a token that requires clearing allowance first, `approve` might fail unexpectedly and cause the subsequent `stack` calls to operate on incorrect allowances or revert. This could lead to failed operations or stuck funds in the proxy.

Remediation
- Set allowance to zero before calling `approve` with a new non-zero amount: first `token.approve(stackAddress, 0)`, then `token.approve(stackAddress, _balance)`; or use `increaseAllowance` pattern if available.
- Consider checking the return value of `approve` and handling non-standard ERC20 implementations explicitly.

