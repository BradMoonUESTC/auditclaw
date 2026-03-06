Summary of review
-----------------

Scope: `stack_wbnb.sol` (withdraw, transfer, sell, reinvest) and `proxy_wbnb.sol` (buyFor transfer to user, donatePool)

What I reviewed:
- Control flow for external token transfers (`token.transfer`, `token.transferFrom`).
- Ordering of state updates vs external calls in `withdraw`, `transfer`, `sell`, `buyFor`, `donatePool`, and proxy wrappers.
- Usage of `onlyBagholders` and `onlyStronghands` modifiers.
- Accounting flow for `payoutsTo_`, `profitPerShare_`, `tokenSupply_`, `tokenBalanceLedger_`.

Findings:
- One high-severity issue (checks-effects-interactions / reentrancy risk) in `transfer()` due to calling `withdraw()` (which does external `token.transfer`) before updating sender and receiver balances and payout trackers. A malicious token contract implementing reentrant callbacks could exploit ordering to cause incorrect balances or double-withdraw.
- One medium-severity issue: `withdraw()` does not check the boolean return of `token.transfer(...)` and proceeds to update internal accounting and emit events regardless. This can result in users being marked as paid when the ERC20 transfer failed or behaved non-standardly. See `findings/002-unchecked-transfer-return.md`.
- Several calls (e.g., `buyFor`, `donatePool`) perform `token.transferFrom` before internal state updates; these are generally safe since they pull tokens into contract, but the proxy logic adds sequences of `transferFrom`, `approve`, and then `stack.buy` / `stack.transfer` which should be carefully sequenced (proxy uses `stack.transfer` after calling `stack.buy` and relies on immediate transfer of ledger tokens).

No other critical issues found in the inspected code paths beyond the transfer-withdraw ordering concern. See findings/ for a detailed write-up and remediation suggestions.
