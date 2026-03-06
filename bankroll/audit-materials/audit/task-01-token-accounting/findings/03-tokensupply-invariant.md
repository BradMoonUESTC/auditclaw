Title: tokenSupply_ vs on-chain balance invariants (fee-on-transfer and non-standard tokens)

Severity: Medium

Affected files/functions:
- `stack_wbnb.sol::purchaseTokens`
- `stack_wbnb.sol::sell`
- `stack_wbnb.sol::totalTokenBalance` (reporting helper)
- `proxy_wbnb.sol::buyFor`, `donatePool`

Root cause

The contract's internal `tokenSupply_` (and per-account `tokenBalanceLedger_`) is computed from call parameters (`_incomingeth`, `_amountOfTokens`) after applying entry/exit fees. There is no explicit reconciliation between `tokenSupply_` and the on-chain token balance (`token.balanceOf(address(this))`). When tokens have transfer-time fees or if some transfers fail/are affected by special logic, the on-chain balance can differ from `tokenSupply_`.

Why this is a problem

- `profitPerShare_` and dividend distributions rely on `tokenSupply_` for pro-rata calculations. If `tokenSupply_` is higher than the actual on-chain balance, distributions may be underfunded or the contract may become unable to honor withdrawals.
- The `proxy_wbnb.sol` attempts to mitigate this by passing the actual token balance to the stack in proxy flows, but direct flows to `stack_wbnb.sol` bypass that safety.

Impact / exploit scenario

- Fee-on-transfer tokens or tokens with hooks that reduce recipient balances can cause the contract to credit more internal tokens than it holds, allowing an attacker to manipulate distribution and potentially cause other users to be unable to withdraw.

Remediation

- Use balance-delta calculations: record `uint previous = token.balanceOf(address(this));` and after `transferFrom` compute `uint received = token.balanceOf(address(this)).sub(previous);` then use `received` for internal accounting.
- Prefer explicit `deposit` pattern where users `transfer` tokens to the contract, then call `buyFor` with no amount; the contract computes the received amount.
- Add invariant checks for debugging/monitoring: e.g., a view function to report `tokenSupply_` vs `token.balanceOf(address(this))` and a `require` in critical functions when mismatch exceeds a threshold.

