Title: Proxy approves and transfers full proxy balance — ERC20 approval/race concerns

Severity: Medium

Affected files/functions:
- `proxy_wbnb.sol` — `buyFor`, `donatePool`
- `stack_wbnb.sol` — `purchaseTokens`, `donatePool` (use of `transferFrom` in Stack is assumed)

Description / root cause
- The proxy contract's `buyFor` and `donatePool` functions transfer ERC20 tokens from the user into the proxy contract using `token.transferFrom(msg.sender, address(this), _buy_amount)` and then call `token.approve(stackAddress, _balance)` where `_balance` is the proxy's entire token balance. Immediately after approving, the proxy calls `stack.buy(_balance)` (or `stack.donatePool(_balance)` in `donatePool`).
- This pattern assumes the Stack contract will call `transferFrom(proxy, stack, amount)` for exactly the `_balance` amount and will not misuse the broader approval that covers the proxy's entire balance. If the token allows re-entrancy during `transferFrom` or if `stack.buy` triggers other token movements or callbacks, the approval of the full proxy balance creates a risk that more than the intended amount could be moved by the Stack contract or by another approved spender during the window.
- Additionally, if the ERC20 token does not follow standard semantics (e.g., charges fees on transfer, modifies balances on approve), the `_balance` may not equal the intended amount and could lead to unexpected behavior.

Impact / exploit scenario
- If `stack` — or another contract with approval — is malicious or buggy, it could drain more tokens than intended from the proxy because the `approve` call grants allowance for the proxy's entire balance. A re-entrancy or callback during `stack.buy` could lead to double-spending where `transferFrom` is called multiple times.
- Using tokens with non-standard transfer behavior (fee-on-transfer) could lead to `_balance` mismatch and incorrect token accounting in the Stack contract.

Remediation
- Approve only the exact amount needed instead of the entire proxy token balance: call `token.approve(stackAddress, _buy_amount)` (or the exact `_balance` intended for the Stack operation), and if multiple operations are needed, reset approvals to zero before changing (patterns to mitigate ERC20 race conditions).
- Consider using `safeApprove` patterns: first `approve(spender,0)` then `approve(spender,amount)` for ERC20s that require it.
- Prefer pull patterns where the Stack contract pulls only the exact amount, or use ERC20s with `increaseAllowance`/`decreaseAllowance` semantics to limit window for misuse.

