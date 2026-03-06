Summary of review


Reviewed: `stack_wbnb.sol` — focus on dividend accounting: `profitPerShare_`, `payoutsTo_`, `allocateFees`, `distribute`, `dividendsOf`, and `dailyEstimate`.

What I reviewed:
- Reconstructed the accounting flows for fees and drip distribution.
- Checked signed/unsigned casts around `payoutsTo_` and `profitPerShare_`.
- Checked time-based arithmetic in `distribute` and `dailyEstimate`.

Findings (created under `findings/`):
- `01-signed-unsigned-dividend.md` (High): casting between `uint256` and `int256` in `dividendsOf` and updates to `payoutsTo_` can overflow/underflow and lead to incorrect dividend calculations or large unintended withdrawals.
- `02-dividendbalance-underflow.md` (Medium): `dividendBalance_` is clamped via `safeSub` while `profitPerShare_` is increased by the computed `profit` regardless of available balance, potentially allowing distribution of more dividends than actually present.

Conclusion:
- The dividend accounting design contains two concrete risks that could be exploited together: unsafe signed/unsigned casts and inconsistent handling of `dividendBalance_` depletion during `distribute`. Both should be remediated before production deployment.

Suggested next steps:
- Change `payoutsTo_` to `uint256` (or avoid casting unsigned -> signed) and ensure all arithmetic stays in unsigned space.
- Fix `distribute` to cap `profit` to `dividendBalance_` (or revert) before updating `profitPerShare_`.
- Add unit/fuzz tests for extreme values and rapid sequences of buys/sells to validate invariants.

