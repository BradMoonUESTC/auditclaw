Title: Approve of entire contract balance allows residual token capture and race conditions

Severity: Medium

Affected files / functions
- `proxy_wbnb.sol` : `donatePool`, `buyFor`
- `stack_wbnb.sol` : `donatePool`, `buyFor` (interaction target)

Description / root cause
- The proxy calls `token.transferFrom(msg.sender, address(this), amount)` to pull tokens from the user into the proxy, then reads `uint _balance = token.balanceOf(address(this));` and calls `token.approve(stackAddress, _balance);` before invoking the stack's function that calls `transferFrom` on the token.
- This pattern approves the entire token balance held by the proxy, including any residual tokens left over from previous interactions, instead of approving only the intended `_amount`.
- Additionally, `token.approve` is called without checking its return value and without first setting the allowance to zero. This can fail or behave unexpectedly with ERC20s that implement the non-standard allowance behavior (require zero->non-zero transition), and may be front-runnable.

Exploit / impact
- If the proxy ever receives tokens from other sources (e.g., accidental transfers, previous failed flows, or maliciously sent tokens), those tokens will be included in the approved amount and can be pulled by the `stackAddress` when the stack calls `transferFrom`. This can lead to unintended transfer of tokens that were not part of the user's intended operation.
- A malicious or buggy `stackAddress` could drain any residual token balance approved by the proxy.
- Race: an attacker could attempt to front-run a user's call by transferring tokens into the proxy before the user's transaction is mined (if possible), increasing the approved balance and causing extra tokens to be pulled by the stack.

Reproduction steps
- User A calls `buyFor` transferring 100 tokens. Proxy has 10 leftover tokens from earlier. Proxy approves 110 to `stackAddress`. Stack pulls 110 and credits user A with 110 worth of stack tokens; the 10 were not intended by user A.

Mitigation / recommendation
- Approve only the exact amount intended to be transferred: set `token.approve(stackAddress, _buy_amount)` (or `_balance` minus previous known balance) rather than the entire `balanceOf(address(this))`.
- Prefer pull pattern elimination: instead of approving and letting the stack call `transferFrom`, consider calling `token.transfer(stackAddress, amount)` where possible so the proxy explicitly transfers only the intended amount (note: this requires stack contract to support `transfer` as token deposit, which currently expects `transferFrom`). If stack can't be changed, approve the exact intended amount and reset approval to zero after the call when appropriate.
- Check and handle `approve` return values. For broader compatibility, use the patterns from OpenZeppelin's `SafeERC20` which handle non-standard tokens.
- Clear prior allowance to zero when adjusting allowances to avoid race conditions: `require(token.approve(stackAddress, 0)); require(token.approve(stackAddress, intendedAmount));` or use `increaseAllowance`/`decreaseAllowance` equivalents where available.

