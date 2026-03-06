Checked files
- `proxy_wbnb.sol` (BankrollNetworkStackProxy)
- `stack_wbnb.sol` (BankrollNetworkStack)

What I inspected
- `BankrollNetworkStackProxy.donatePool`, `.buyFor`, `.buy`, and fallback
- Corresponding flows in `BankrollNetworkStack.donatePool`, `.buyFor`, `.buy`, `.transfer`

High level notes
- Proxy pattern: user -> proxy (transferFrom) -> proxy approves stack -> stack.transferFrom(proxy->stack) -> stack credits internal ledger -> proxy transfers stack internal tokens to user.
- Proxy uses `token.balanceOf(address(this))` and approves the entire balance to the stack rather than only the freshly transferred amount.
- `token.approve` is called without checking its return and without zeroing prior allowance.
- Both proxy and stack assume ERC20 functions return `bool` and use `require(token.transferFrom(...))` which is incompatible with some non-standard tokens.

Quick verification checklist performed
- Confirmed call sequences and who the `msg.sender` is in each contract.
- Verified that stack's `donatePool` and `buyFor` call `token.transferFrom(msg.sender, address(this), amount)` (so they pull from the proxy after approve).
- Confirmed fallback reverts on any plain native transfer (`require(false)`).

