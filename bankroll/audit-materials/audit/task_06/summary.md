Scope
- Files reviewed: `stack_wbnb.sol`.
- Targeted functions/vars: `distribute()`, `dailyEstimate()`, `balanceInterval`, `distributionInterval`, `lastPayout`.

What I reviewed
- Reconstructed how the contract accumulates and drips dividend tokens: fees are added to `dividendBalance_`, `allocateFees()` keeps most of the fee in `dividendBalance_` and credits instant portions to `profitPerShare_`.
- `distribute()` periodically drips a portion of `dividendBalance_` into `profitPerShare_` proportionally to time elapsed since `lastPayout`.

Findings summary
- I identified two concrete issues:
  - Potential arithmetic overflow/precision problems when multiplying `profit` by `magnitude` or when computing per-account dividends using `profitPerShare_ * tokenBalanceLedger_[_addr]` because these multiplications are not protected by SafeMath and use unchecked uint256 arithmetic under Solidity 0.4.25.
  - Timestamp manipulation and granularity concerns: `distributionInterval` is set to 2 seconds, enabling frequent `distribute()` calls; because `distribute()` uses `now` and is triggered during public actions (buy/sell/withdraw/reinvest/transfer), a miner or attacker could influence block timestamps and call ordering to alter `profit` awarded in a given block.

Additionally, I added a third finding covering an "overdrip" inconsistency where `profitPerShare_` can be increased by an amount larger than the remaining `dividendBalance_` when `lastPayout` is stale, causing per-share accounting to exceed available funds. The finding describes the root cause and suggests capping `profit` by `dividendBalance_` before applying updates.

Next steps
- Written full findings in `findings/` with severity, impacted functions, root cause, impact, and suggested remediations.
