Title: Incompatible assumptions about ERC20 transfer/approve return values and fee-on-transfer tokens

Severity: Medium

Affected files / functions
- `proxy_wbnb.sol`: `donatePool`, `buyFor` (use `require(token.transferFrom(...))` and `token.approve(...)` without checking returns)
- `stack_wbnb.sol`: `donatePool`, `buyFor`, `withdraw` (assume `token.transfer` returns `bool`)

Description / root cause
- Both proxy and stack assume ERC20 token functions `transfer`, `transferFrom`, and `approve` return `bool` and use `require(token.transferFrom(...))` for safety. However, some tokens (older or non-standard) do not return a boolean and instead revert on failure or return nothing. Using `require(token.transferFrom(...))` with such tokens will break or behave unexpectedly.
- The proxy and stack do not account for fee-on-transfer tokens where the amount received by the contract is less than the amount sent due to transfer fees. The proxy reads `balanceOf(address(this))` and approves that amount, but if the token levies fees during `transferFrom`, the credited balance may be lower than expected and flows could underfund the stack's expectations.

Exploit / impact
- Using a token that does not return `bool` may cause the `require` checks to revert or to misinterpret the success of calls, breaking the buy/donate flows for that token.
- Fee-on-transfer tokens can cause mismatches between the amount the user intended to deposit and the actual amount taken — potentially leading to lower credit to the buyer and residual accounting mismatches.

Reproduction steps
- Deploy with a token that implements `transferFrom` without a return value (older ERC20). Calls that `require(token.transferFrom(...))` will revert or fail to compile against that token's ABI.
- Use a token with transfer fees; call `buyFor` with X tokens approved. The proxy will `transferFrom` X to the proxy but the proxy's `balanceOf` may be X-fee; the stack will receive X-fee when it pulls tokens. This reduces the credited amount compared to expected.

Mitigation / recommendation
- Use OpenZeppelin's `SafeERC20` wrappers which handle optional return values safely (i.e., treat missing return as success if call didn't revert) and emit a clearer failure path.
- For tokens with transfer fees, the contract should avoid assuming a 1:1 amount transfer. Consider calculating net received amount by checking `before = token.balanceOf(address(this))`, performing `transferFrom`, `after = token.balanceOf(address(this))`, then using `after - before` as the actual amount received.
- Replace `require(token.transferFrom(...))` with proper safe wrapper calls and ensure `approve` is checked for return or handled via `SafeERC20.safeApprove`.

