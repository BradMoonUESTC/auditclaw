Review summary — Token Accounting and Supply Consistency

What I reviewed

- Task: `audit-materials/decompose/tasks/task-01-token-accounting/task.json`.
- Contracts: `stack_wbnb.sol` and `proxy_wbnb.sol`.

Scope and focus

- Verified consistency between `tokenSupply_`, `tokenBalanceLedger_`, and actual ERC20 token balances (`token.balanceOf(address(this))`).
- Traced flows: `buyFor`, `purchaseTokens`, `withdraw`, `sell`, `transfer`, and proxy-mediated `buyFor`/`donatePool`.

High-level findings

- Finding 1 (high): Mismatch risk between amounts used for internal accounting and actual tokens received when buys/donations are routed through `proxy_wbnb.sol` vs direct `stack_wbnb.sol` calls. `stack_wbnb.sol::buyFor` trusts the `buy_amount` argument while `proxy_wbnb.sol` forwards actual `token.balanceOf`.

- Finding 2 (high): `withdraw()` in `stack_wbnb.sol` calls `token.transfer(...)` without checking the return value; internal accounting is updated before transfer success is confirmed, potentially allowing users to be marked as paid while tokens remain in contract.

- Finding 3 (medium): `tokenSupply_` updates are derived solely from arithmetic on the provided `_incomingeth` after fees; however, interactions with tokens that have fee-on-transfer or non-standard transfer semantics can cause an inconsistent on-chain `token.balanceOf(address(this))` vs `tokenSupply_` ledger leading to stuck funds or mis-accounted dividends.

Next steps and recommendations

- Record findings (written in `findings/`).
- Recommend consistent use of actual received token amounts (i.e., read `token.balanceOf(address(this))` before accounting) in `stack_wbnb.sol` purchase/donate entrypoints or ensure proxy always forwards exact amounts.
- Add return-value checks for `token.transfer` and `token.approve` and consider using `SafeERC20` style wrappers for compatibility with non-standard ERC20s and fee-on-transfer tokens.

