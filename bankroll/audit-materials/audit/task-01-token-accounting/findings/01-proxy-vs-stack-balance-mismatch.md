Title: Proxy vs Stack — balance/amount mismatch on buy/donate

Severity: High

Affected files/functions:
- `proxy_wbnb.sol::buyFor`
- `proxy_wbnb.sol::donatePool`
- `stack_wbnb.sol::buyFor`
- `stack_wbnb.sol::donatePool`

Root cause

There are two different assumptions about how much token value should be used for internal accounting after a user calls `transferFrom`:

- `proxy_wbnb.sol` transfers tokens into the proxy, then reads `token.balanceOf(address(this))` (the actual on-chain balance) and approves/passes that balance to the stack.
- `stack_wbnb.sol::buyFor` and `stack_wbnb.sol::donatePool` assume the `_buy_amount` / `amount` parameter equals the tokens actually received and use the parameter in `purchaseTokens` and to increment `dividendBalance_`.

Why this is a problem

- If the token implements fee-on-transfer (i.e., sender has X tokens debited but recipient receives less due to burn/fee), or if a previous residual balance existed in the proxy, the `_buy_amount` provided by an external caller to `stack.buyFor` may not match the actual tokens received by the contract.
- For proxy-mediated buys (`proxy_wbnb.sol::buyFor`) the stack receives an argument equal to the proxy's token balance (good), but direct calls to `stack_wbnb.sol::buyFor` use the caller-supplied `buy_amount` which may be larger than the actual received tokens (if the token charges transfer fees) resulting in tokenSupply_ and tokenBalanceLedger_ being incremented by an amount that does not match tokens held by the contract.

Impact / exploit scenario

- With a fee-on-transfer token, users calling `stack.buyFor(..., buy_amount)` directly would cause the contract to mint internal tokens corresponding to the full `buy_amount`, but the contract's ERC20 balance would be less. This leads to:
  - Divergence between `tokenSupply_` and actual `token.balanceOf(address(this))`.
  - Future dividend distributions (calculated from `dividendBalance_` and `profitPerShare_`) may be skewed because `profitPerShare_` uses `tokenSupply_` for per-share scaling.
  - Potential inability to cover withdrawals if `tokenSupply_` > actual token balance (users marked as owning tokens that the contract doesn't hold), leading to funds shortfall.

Remediation

- Always use the actual received token amount (read `token.balanceOf(address(this))` before approving or calling internal accounting) in entrypoints that accept token transfers, or compute the received amount by reading the balance delta (previous balance -> new balance).
- Alternatively, switch to an explicit two-step flow where the caller first `transfer` tokens to the contract and then calls `buyFor` with zero-amount, and the contract computes the actual received amount internally.
- Document the token compatibility assumptions, or restrict supported tokens to standard ERC20s without fee-on-transfer behavior.

