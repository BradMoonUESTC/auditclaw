Checked files and key observations

- Reviewed task file: `audit-materials/decompose/tasks/task-01-token-accounting/task.json` (target: `stack_wbnb.sol`, `proxy_wbnb.sol`).
- Reviewed request: `audit-materials/request.md`.
- Reviewed source contracts: `stack_wbnb.sol` and `proxy_wbnb.sol`.

Code areas inspected

- `stack_wbnb.sol`:
  - `donatePool(uint amount)` (uses `token.transferFrom` and adds `amount` to `dividendBalance_`).
  - `buyFor(address,uint buy_amount)` (calls `token.transferFrom(_customerAddress, address(this), buy_amount)` then uses `buy_amount` for accounting via `purchaseTokens`).
  - `purchaseTokens(address,uint256)` (increments `tokenSupply_` and `tokenBalanceLedger_` by computed `_amountOfTokens` derived from `_incomingeth` parameter).
  - `withdraw()` (updates payouts and then calls `token.transfer(_customerAddress,_dividends)` without checking return value).
  - `totalTokenBalance()` helper uses `token.balanceOf(address(this))`.

- `proxy_wbnb.sol`:
  - `buyFor` transfers tokens into proxy, uses `token.balanceOf(address(this))` to determine `_balance`, approves stack with that balance, calls `stack.buy(_balance)` and transfers internal stack tokens to customer.
  - `donatePool` transfers tokens into proxy, reads `token.balanceOf`, approves, then calls `stack.donatePool(_balance)`.

Immediate takeaways

- There are inconsistent patterns for how the "received" token amount is determined after `transferFrom`:
  - `proxy_wbnb.sol` uses `token.balanceOf(address(this))` (actual received balance) before approving and passing an amount to the stack.
  - `stack_wbnb.sol::buyFor` and `donatePool` assume the `buy_amount` or `amount` param equals the tokens actually received and use that value for internal accounting.

- `withdraw()` does not check the boolean return from `token.transfer` and updates internal accounting regardless.

Files and functions noted for findings generation.

