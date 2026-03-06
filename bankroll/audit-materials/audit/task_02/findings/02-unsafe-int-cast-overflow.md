Title: Unsafe uint256 -> int256 casts for `payoutsTo_` and potential signed overflow

Severity: High

Affected files/functions:
- `stack_wbnb.sol`: `purchaseTokens()`, `sell()`, `reinvest()`, `withdraw()`, `transfer()`, `dividendsOf()`

Issue

The contract stores per-address payout tracking in `mapping(address => int256) payoutsTo_;`. Several places compute values in `uint256` (e.g. `profitPerShare_ * _amountOfTokens`, `_dividends * magnitude`) and then cast them to `(int256)` before adding/subtracting to `payoutsTo_`:

- `payoutsTo_[_customerAddress] += (int256) (_dividends * magnitude);` (in `reinvest` and `withdraw`)
- `int256 _updatedPayouts = (int256) (profitPerShare_ * _amountOfTokens + (_taxedeth * magnitude));` (in `sell`)
- `int256 _updatedPayouts = (int256) (profitPerShare_ * _amountOfTokens);` (in `purchaseTokens`)

These casts can overflow the signed 256-bit range if the computed uint256 is greater than int256 max (2^255 - 1). While `profitPerShare_` and magnitudes are intended to be small, token supply and profit scaling may grow large over time and overflow is possible.

Root cause

Direct casting from `uint256` to `int256` without bounds checking is unsafe. Solidity 0.4.25 will silently wrap for such casts, producing negative numbers and corrupting dividend accounting.

Exploit / Impact

- An overflow during these casts can cause payout accounting to become corrupted for an address (or globally when `profitPerShare_` is used). This could allow attackers to siphon dividends, prevent users from withdrawing correctly, or induce negative dividends.

Remediation

- Avoid direct casts of large arithmetic expressions into `int256`.
- Option A: Keep `payoutsTo_` as `int256` but add explicit checks before casting, ensuring the uint256 value is <= uint256(int256_max). Use a SafeCast helper that reverts on out-of-range.
- Option B: Change accounting to use only `uint256` math for payouts and dividends (e.g., store `payoutsTo_` as `uint256` and adjust formulas accordingly), or use `SignedSafeMath` with explicit signed types and checks.
- Add unit tests that simulate large tokenSupply_ and profitPerShare_ to verify no overflow occurs.

