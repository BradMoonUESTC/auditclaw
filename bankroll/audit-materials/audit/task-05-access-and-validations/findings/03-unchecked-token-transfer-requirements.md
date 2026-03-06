# 03 - Reliance on external token behavior without checks for non-standard ERC20

Severity: Low-Medium

Affected files
- `stack_wbnb.sol` — functions: `donatePool`, `buyFor`, `withdraw` (calls `token.transfer`), `buy`/`buyFor` use `transferFrom`
- `proxy_wbnb.sol` — calls `token.transferFrom`, `token.approve`

Description / root cause
- The contracts assume the token implements standard ERC20 semantics that return boolean values for `transfer` / `transferFrom` and that `approve` works as expected. While some `require` checks exist (the proxy wraps `transferFrom` in `require`), the stack contract calls `token.transfer(_customerAddress,_dividends);` without checking the return value. If the token is non-standard (doesn't return bool) or returns false on failure, the call could silently fail (in older Solidity versions the return value is ignored). Additionally, `token.transferFrom` is used under the assumption it reverts if not allowed.

Exploit / impact
- If interacting with a non-standard token or a token with hooks (which may revert), transfers could fail silently or behave unexpectedly, causing users to believe they withdrew tokens when they did not. This is mostly a compatibility risk but can lead to loss of funds or stuck balances.

Recommendation
- Use OpenZeppelin's `SafeERC20` wrappers (or manual low-level calls) to ensure transfer/transferFrom/approve return success or revert on failure.
- Check return values explicitly where possible, or document supported token standards.

