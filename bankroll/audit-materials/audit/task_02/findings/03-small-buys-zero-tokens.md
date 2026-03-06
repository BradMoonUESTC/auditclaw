Title: Very small buys can result in zero tokens due to fee rounding

Severity: Medium

Affected files/functions:
- `stack_wbnb.sol`: `purchaseTokens()`, `calculateTokensReceived()`

Issue

`purchaseTokens()` calculates `_undividedDividends = _incomingeth * entryFee_ / 100` and then `_amountOfTokens = _incomingeth - _undividedDividends`. When `_incomingeth` is very small, integer division truncation can make `_undividedDividends` zero or equal to `_incomingeth`, producing `_amountOfTokens` equal to `_incomingeth` or zero respectively. The function requires `_amountOfTokens > 0`, so tiny buys that result in zero tokens will revert.

Root cause

Use of integer division and a flat percentage fee causes rounding/truncation; there is no minimum buy enforcement nor user feedback mechanism other than a revert on zero tokens.

Exploit / Impact

- Users attempting micro-buys may get transactions reverted. If a frontend doesn't prevent tiny buys, users will pay gas and the transaction will fail.
- In edge arithmetic cases, if rounding leads to 1 wei of fee and subtraction results in zero tokens, this can be used to DDOS by forcing many failing transactions, wasting gas for victims.

Remediation

- Add a minimum buy amount check (e.g., require(_incomingeth >= MIN_BUY_AMOUNT)) with a documented threshold.
- Consider applying fee rounding that favors buyer (e.g., compute taxed = _incomingeth * (100 - entryFee_) / 100) to avoid full-zero results, or use a higher precision scaling factor for fee calculations.
- Improve frontend to block tiny buys and show the minimum required funds for a purchase.

