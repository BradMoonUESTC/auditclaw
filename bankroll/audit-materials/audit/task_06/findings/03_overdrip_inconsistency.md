Title: Overdrip inconsistency — profitPerShare_ can exceed available dividendBalance_
Severity: Medium

Affected files / functions
- `stack_wbnb.sol` — `distribute()` and related dividend accounting (`profitPerShare_`, `dividendBalance_`).

Description / root cause
- In `distribute()` the contract computes a per-second `share` from the current `dividendBalance_`, then multiplies `share` by the elapsed seconds to obtain `profit`:
  - `uint256 share = dividendBalance_.mul(payoutRate_).div(100).div(24 hours);`
  - `uint256 profit = share * now.safeSub(lastPayout);`
- The contract then subtracts `profit` from `dividendBalance_` using `safeSub`, which clamps to zero when `profit > dividendBalance_`.
- However, the contract always applies the full `profit` to `profitPerShare_`:
  - `profitPerShare_ = SafeMath.add(profitPerShare_, (profit * magnitude) / tokenSupply_);`
- If `profit` is larger than `dividendBalance_` (for example when `lastPayout` is stale and a long time has elapsed) `dividendBalance_` becomes zero but `profitPerShare_` is increased as if the full `profit` were paid out. This causes the per-share accounting to reflect more distributed tokens than are actually available in the pool.

Exploit / impact
- This creates an inconsistency between the recorded per-share distribution (`profitPerShare_`) and the actual `dividendBalance_`. As a result:
  - Subsequent calls to `dividendsOf()` and withdrawals will treat holders as if more tokens were distributed, potentially allowing them to withdraw balances that are not backed by `dividendBalance_` (depending on timing and interactions with other state changes).
  - The pool accounting integrity is compromised; actors can manipulate call timing so a large `profit` is computed and applied while `dividendBalance_` is clamped to zero.

Suggested remediation
- Ensure `profit` is capped by the available `dividendBalance_` before applying it to `profitPerShare_`. For example:
  - `uint256 profit = share * now.safeSub(lastPayout);`
  - `if (profit > dividendBalance_) { profit = dividendBalance_; }`
  - then apply `profitPerShare_` update and subtract `profit` from `dividendBalance_`.
- Alternatively, compute `profit` using a numerator/denominator formulation that keeps the paid amount consistent with the remaining balance, or update `share` calculation to use a precise fraction of the pool, and guard against stale `lastPayout` values (e.g., cap maximum elapsed seconds allowed).
- Add unit tests for long pauses between `lastPayout` and the next distribute call to assert `dividendBalance_` never goes negative and `profitPerShare_` is always consistent with remaining funds.

