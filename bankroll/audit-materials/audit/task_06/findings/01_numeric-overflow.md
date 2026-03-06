Title: Unchecked multiplications can overflow when computing profits and per-account dividends
Severity: High

Affected files / functions
- `stack_wbnb.sol` — `distribute()`, `dailyEstimate()`, `dividendsOf()`, `purchaseTokens()`, `sell()` (calculations involving `magnitude`, `profitPerShare_`, and token balances).

Description / root cause
- The contract implements fixed-point dividend accounting using a large `magnitude = 2 ** 64` and a `profitPerShare_` accumulator. Several critical multiplications are performed without using SafeMath and thereby rely on unchecked uint256 arithmetic in Solidity 0.4.25. Examples:
  - In `distribute()`: `profitPerShare_ = SafeMath.add(profitPerShare_, (profit * magnitude) / tokenSupply_);` — `profit * magnitude` is computed without overflow protection and may overflow if `profit` is large.
  - In `dividendsOf()`: `(int256) (profitPerShare_ * tokenBalanceLedger_[_customerAddress])` multiplies `profitPerShare_` by an account balance without checks; intermediate result may overflow uint256 before being cast to int256.
- Although some uses wrap later with SafeMath when adding to `profitPerShare_`, the raw multiplication `profit * magnitude` and `profitPerShare_ * tokenBalance` are potential overflow points. Since `magnitude` is 2^64 (~1.84e19) and token balances and profit can be large (contract token balance may be up to uint256), this can produce values that exceed 2^256-1.

Exploit / impact
- If an overflow occurs when computing `(profit * magnitude)`, the value used to update `profitPerShare_` can wrap around, causing the per-share profit accounting to be incorrect. This could lead to:
  - Incorrect dividend allocations: some or all holders receive incorrect dividend amounts (too large or negative after cast/truncation).
  - Ability for an attacker to cause an imbalance in `dividendBalance_` vs recorded `profitPerShare_`, potentially enabling draining or permanent loss of funds.
  - Corruption of `payoutsTo_` arithmetic when used in conjunction with other operations, leading to under- or over-payment on withdraw/reinvest.

Steps to reproduce (conceptual)
- Increase `dividendBalance_` to a very large value (near uint256 max) and call `distribute()` when `tokenSupply_` is small, so `profit` is large. The multiplication `profit * magnitude` may overflow.
- Alternatively, set `profitPerShare_` large and hold a large token balance; call `dividendsOf()` to trigger `profitPerShare_ * tokenBalanceLedger_[_addr]` multiplication overflow.

Suggested remediation
- Use SafeMath for all large multiplications and intermediate steps: compute `profit.mul(magnitude).div(tokenSupply_)` using SafeMath.mul and SafeMath.div to ensure reverts on overflow.
- Alternatively, re-order arithmetic to divide first where possible: `(profit / tokenSupply_).mul(magnitude)` when `profit` >= `tokenSupply_` to reduce intermediate sizes.
- Add bounds checks and unit tests that simulate large balances and profits to ensure no overflow paths exist.
- Consider using Solidity >=0.8.0 which has built-in overflow checks, or use a dedicated library for fixed-point arithmetic that guards intermediate operations.

