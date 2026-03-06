Title: Signed/Unsigned conversions in dividend accounting

Severity: High

Files: `stack_wbnb.sol`

Affected functions / variables:
- `dividendsOf`
- `purchaseTokens` / `sell` / `withdraw` (use `payoutsTo_` updates)
- variables: `profitPerShare_` (uint256), `payoutsTo_` (int256), `magnitude` (uint256)

Root cause:
The contract stores cumulative per-share profit in an unsigned `uint256 profitPerShare_` and per-account accumulators in a signed `int256 payoutsTo_`. `dividendsOf` computes:

    (uint256) ((int256) (profitPerShare_ * tokenBalanceLedger_[addr]) - payoutsTo_[addr]) / magnitude

This involves casting a large unsigned product into `int256`. If `profitPerShare_ * balance` exceeds the max `int256` (2^255 -1), the cast will wrap/overflow leading to negative or unexpected values. Conversely, `payoutsTo_` being negative or very large positive can cause the subtraction to underflow/overflow when converted back to `uint256`.

Impact / exploit:
- An attacker could manipulate `profitPerShare_` and/or `payoutsTo_` via repeated calls that increase `dividendBalance_` or trigger `distribute` such that the casted values overflow the signed 256-bit range, causing `dividendsOf` to return extremely large values or revert on invalid casts. This could allow extraction of large token amounts via `withdraw` or `reinvest` that exceed intended balances, draining the dividend pool or contract token balance.

Evidence in code:
- In `purchaseTokens` and `sell`, updates to `payoutsTo_` and `profitPerShare_` rely on multiplications by `magnitude` and `profitPerShare_` which can grow unbounded relative to `int256` bounds.

Remediation:
- Avoid casting large unsigned values into signed types. Use only unsigned (`uint256`) accounting for both per-share profit and per-account accumulators. Alternatively, ensure bounds checks prevent `profitPerShare_` from ever growing beyond `int256` max (not practical).
- Change `payoutsTo_` type to `uint256` and adjust arithmetic accordingly, or perform safe checked conversions with explicit require checks before casts.
- Add unit tests to ensure `profitPerShare_ * tokenBalance` never exceeds signed bounds, and fuzz tests for many distributions.

