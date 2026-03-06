Title: Timestamp dependency and very small distributionInterval enable miner/timestamp manipulation and frequent drip abuse
Severity: Medium

Affected files / functions
- `stack_wbnb.sol` — `distribute()`, `balanceInterval`, `distributionInterval`, `dailyEstimate()`

Description / root cause
- `distribute()` uses `now` (alias for `block.timestamp`) to compute time elapsed since `lastPayout` and to determine when to emit `onBalance`. The contract calculates a per-second `share` via `dividendBalance_.mul(payoutRate_).div(100).div(24 hours)`, then computes `profit = share * now.safeSub(lastPayout)` and subtracts `profit` from `dividendBalance_` to drip funds.
- `distributionInterval` is set to `2 seconds`. Because `distribute()` is triggered on many public actions (buy, sell, withdraw, reinvest, transfer), an attacker or miner can manipulate the effective `now` when including transactions or reorder transactions to cause more or less profit to be paid out than intended.
- Additionally, the small `distributionInterval` allows frequent invocations of `distribute()` (every ~2 seconds), creating a potential DoS/gas and spam vector where many calls update state and emit events.

Impact / exploit scenarios
- Miner timestamp manipulation: a miner building a block can slightly change `block.timestamp` (within consensus limits) and include or exclude transactions to maximize or minimize `now.safeSub(lastPayout)` relative to other blocks, affecting `profit` computed for that block. While timestamps cannot be arbitrarily set, small adjustments can influence payouts at scale across many blocks.
- Frequent clamping: calling `distribute()` frequently with tiny time deltas causes `profit` to be very small (often zero if division truncates), leading to unnecessary gas use and event emission, and may cause rounding effects where small repeated payouts gradually drain `dividendBalance_` due to truncation.
- Rounding and truncation: per-second `share` is computed using integer division; for short elapsed intervals, `profit` might be zero, or repeated rounding may transfer slightly less than expected leaving residual `dividendBalance_` which could be stuck or misaccounted.

Suggested remediation
- Increase `distributionInterval` to a more reasonable value (e.g., 15 minutes or 1 hour) to reduce call frequency and minimize timestamp granularity exploitation.
- Avoid relying on `now` for economic-critical precise calculations where miners can influence outcomes. Consider computing drips based on block.number and a fixed block-time estimate, or use pull-based claiming that does not depend on block timestamp arithmetic for fairness-critical allocations.
- Protect `distribute()` from being called too frequently by adding reentrancy guards or per-caller cooldowns if necessary, and ensure that tiny `profit` values are handled (e.g., require `profit > 0` before updating state) to avoid gas waste.
- Add tests demonstrating timestamp skew effects and rounding behavior with various `distributionInterval` sizes.

