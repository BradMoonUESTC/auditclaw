Title: buyPrice() and calculateTokensReceived() disagree with purchase logic

Severity: High

Affected files/functions:
- `stack_wbnb.sol`: `buyPrice()`, `calculateTokensReceived()`, `purchaseTokens()`

Issue

The `buyPrice()` function returns the price of 1 token as `1e18 + fee`, i.e. it adds the entry fee to the base price. In contrast, the actual purchase path (`purchaseTokens`) computes the number of tokens by subtracting the fee from the incoming amount:

- `purchaseTokens`: _amountOfTokens = _incomingeth - undividedDividends
- `calculateTokensReceived`: does the same subtraction
- `buyPrice()`: computes `_taxedeth = _eth + _dividends` and returns `_taxedeth`

Root cause

`buyPrice()` uses `SafeMath.add(_eth, _dividends)` when it should present the effective amount of tokens the buyer receives per unit of token currency. This yields a misleading, inconsistent value relative to the real purchase calculation where fees are removed from the buyer's funds.

Exploit / Impact

- Frontends and analytics relying on `buyPrice()` will display an incorrect price (higher than actual expected tokens per spend), confusing users and possibly causing UX or accounting errors.
- Automated systems using `buyPrice()` for quoting or slippage calculations could misprice orders and lead to unexpected failures or user losses.

Remediation

- Change `buyPrice()` to reflect net tokens per unit of token currency consistent with `calculateTokensReceived` and `purchaseTokens`. For example, compute and return the taxed (post-fee) amount: `_taxedeth = SafeMath.sub(_eth, _dividends)`.
- Update documentation and frontend code to rely on `calculateTokensReceived` which is correct, or deprecate `buyPrice()`.

