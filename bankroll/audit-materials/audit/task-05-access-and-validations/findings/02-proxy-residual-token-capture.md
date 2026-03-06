# 02 - Proxy captures residual tokens and approves full balance to stack

Severity: Medium

Affected files / functions
- `proxy_wbnb.sol` — `donatePool(uint amount)`, `buyFor(address _customerAddress, uint _buy_amount)`

Description / root cause
- The proxy pulls tokens from `msg.sender` into the proxy contract via `transferFrom`. After the transfer it reads the full `token.balanceOf(address(this))` and calls `token.approve(stackAddress, _balance)` and then calls into the stack contract (`stack.buy(_balance)` or `stack.donatePool(_balance)`). This design captures any residual token balance already present in the proxy (from prior failed or partial operations, or from a different user) and mixes it with the current user's deposit.

- The approval grants the stack contract permission to transfer the entire proxy balance, which may include tokens not intended for the current caller. While the proxy immediately calls `stack.buy` and then transfers the resulting internal stack tokens to the intended recipient, the pattern can cause mis-attribution of funds if concurrent transfers or leftover tokens exist.

Exploit / impact
- A prior user or attacker could transfer tokens into the proxy (e.g., by directly sending tokens to the proxy address). When a legitimate user later calls `buyFor`, their transfer will be combined with the residual balance and approved to the stack; the stack will buy tokens for the combined amount and the proxy will then transfer the entire bought stack-token balance to the caller. The residual tokens thus become purchasable into the caller's account, allowing an attacker to seed the proxy and have later callers buy with that seed. This is an economic front-running / fund-mixing issue and can lead to theft of value contributed earlier.

Recommendation
- Do not use `token.balanceOf(address(this))` to determine the amount to approve/use. Instead, track the exact amount transferred during the call. For example:
  - Use a local variable `_received = _buy_amount` (or compute balance before/after transfer) and approve only `_received`.
  - After calling `transferFrom`, compute `_received = token.balanceOf(address(this)) - _previousBalance` to get exact transferred amount.
- Consider using `approve` to set allowance to the exact amount and then immediately set it back to zero after the call (defensive pattern).
- Reject or safely handle any stray tokens (e.g., require proxy balance to be zero before accepting user deposits, or provide an admin sweep with clear access controls).

