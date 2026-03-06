Title: dividendBalance_ subtraction and silent clamping

Severity: Medium

Files: `stack_wbnb.sol`

Affected functions / variables:
- `distribute`
- variable: `dividendBalance_`

Root cause:
The `distribute` function computes `profit = share * now.safeSub(lastPayout);` and then updates `dividendBalance_ = dividendBalance_.safeSub(profit);` where `safeSub` returns zero when `profit > dividendBalance_` instead of reverting. This silently clamps `dividendBalance_` to zero while still proceeding to increase `profitPerShare_` using the computed `profit` value even if the actual available balance was smaller.

Impact / exploit:
- If `profit > dividendBalance_`, `safeSub` will set `dividendBalance_` to zero, but `profitPerShare_` is increased by `(profit * magnitude) / tokenSupply_`. This effectively allows distributing more dividends (on paper) than the contract actually held, inflating `profitPerShare_` and allowing users to withdraw nonexistent tokens from the contract via `withdraw`/`reinvest`, potentially draining other balances.

Evidence in code:
- `dividendBalance_ = dividendBalance_.safeSub(profit);`
- Immediately after, `profitPerShare_ = SafeMath.add(profitPerShare_, (profit * magnitude) / tokenSupply_);`

Remediation:
- Replace `safeSub` with an explicit require: `require(profit <= dividendBalance_)` or compute `actualProfit = min(profit, dividendBalance_)` and use `actualProfit` for both the subtraction and the `profitPerShare_` update to ensure accounting consistency.
- Add checks and tests for cases where `distributionInterval` is large or `dividendBalance_` small.

