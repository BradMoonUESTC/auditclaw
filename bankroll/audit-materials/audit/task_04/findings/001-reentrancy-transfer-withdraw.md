Title: Reentrancy / Checks-Effects-Interactions issue in `transfer()` via `withdraw()` external call

Severity: High

Files / functions:
- `stack_wbnb.sol` — `transfer(address _toAddress, uint256 _amountOfTokens)`
- `stack_wbnb.sol` — `withdraw()` (called from `transfer`)

Description / root cause:
The `transfer()` function calls `withdraw()` when `myDividends() > 0`. The `withdraw()` function updates `payoutsTo_` but then performs an external call to `token.transfer(_customerAddress, _dividends)` before completing other local updates related to balances and dividend accounting that `transfer()` performs after calling `withdraw()`.

Because `token.transfer(...)` is an external call to an ERC20 token contract, a malicious token implementation could include a reentrant callback (e.g., reusing ERC777 hooks, or a token `transfer` that calls back into `stack.transfer` or `stack.withdraw`) and cause state transitions in the `Stack` contract to occur in an unexpected order. In particular, a reentrant call occurring during `withdraw()` could re-enter `transfer()` or other functions and manipulate `tokenBalanceLedger_`, `payoutsTo_`, or `tokenSupply_` while the original `transfer()` has not yet finished updating those values.

Impact / exploit scenario:
- An attacker could craft a token whose `transfer` implementation calls back into the `Stack` contract during `withdraw()`. If reentrancy occurs before `transfer()` has updated `tokenBalanceLedger_[_customerAddress]` and `payoutsTo_` for the token movement, the reentrant call may observe inconsistent balances and withdraw more than permitted, or re-trigger `withdraw()` leading to double payouts.
- Depending on which functions the malicious token calls during reentry, the attacker may be able to drain dividend balances or cause incorrect reward distribution.

Proof / code references:
- `transfer()` (excerpt):
  - checks balance and then: if (myDividends() > 0) { withdraw(); }
  - after withdraw returns, updates `tokenBalanceLedger_[_customerAddress]` and `tokenBalanceLedger_[_toAddress]` and adjusts `payoutsTo_` accordingly.
- `withdraw()` (excerpt):
  - computes `_dividends = myDividends()`
  - updates `payoutsTo_[_customerAddress] += _dividends * magnitude;`
  - calls `token.transfer(_customerAddress, _dividends);`
  - updates stats and emits events

Remediation suggestion:
- Do not perform external calls (token.transfer) while holding state that will be updated later in the calling function. Reorder operations so that `transfer()` finishes updating `tokenBalanceLedger_` and `payoutsTo_` for both parties before any external transfer occurs, or adopt a pull-over-push pattern where withdrawals are not triggered automatically inside `transfer()`.
- Specific fixes:
  1. Remove the automatic in-line `withdraw()` call from `transfer()`. Instead, either:
     - require users to call `withdraw()` separately (safer), or
     - perform an internal call that moves dividends into a withdrawable mapping (credit) without external calls, then let the caller externally pull funds.
  2. If keeping the automatic withdrawal is necessary, ensure `transfer()` first performs all local state updates (balances, payoutsTo_) and only after that calls `withdraw()` but modify `withdraw()` to separate computing and transferring so the actual external `token.transfer` happens after `transfer()`'s state updates.
  3. Add a reentrancy guard (mutex) to prevent reentrancy during critical sections.

Notes:
- `withdraw()` already updates `payoutsTo_` before doing the external `token.transfer`, which reduces risk for double-paying within `withdraw()` itself, but calling `withdraw()` from `transfer()` still leaves a window because `transfer()` hasn't yet updated balances/payouts for the token movement.
- The `reinvest()` function is safe because it only updates `payoutsTo_` and calls internal `purchaseTokens()` (no external token transfer).

