What I reviewed

- Reviewed `stack_wbnb.sol` end-to-end for functions: `purchaseTokens`, `buyFor`, `buyPrice`, `sellPrice`, `calculateTokensReceived`, `calculateethReceived`, `allocateFees`, and `distribute`.
- Checked interactions of `profitPerShare_`, `payoutsTo_`, and `dividendBalance_` updates.

Findings summary

- High: `buyPrice()` is implemented inconsistently with actual purchase logic — it adds the fee instead of subtracting it; frontend using this will misrepresent costs. See `findings/01-buyprice-incorrect.md`.
- High: Unsafe casts from `uint256` to `int256` when updating `payoutsTo_` and potential overflow of signed range when profitPerShare_ * tokenBalance is large. See `findings/02-unsafe-int-cast-overflow.md`.
- Medium: Very small `buy_amount` can become zero tokens after fee subtraction; tokens are 1:1 with token units so tiny buys may be dropped. See `findings/03-small-buys-zero-tokens.md`.

No duplicate findings with `audit-materials/audit/task-01-token-accounting` were found; those focus on proxy/stack mismatch and withdraw transfers.

Next steps

- Recommend reconciling `buyPrice()` with `purchaseTokens` logic and updating frontend helpers.
- Add overflow guards or use signed integer widening with checks before casting to `int256` or switch `payoutsTo_` to `int256` range checking via SafeCast.
- Consider documenting minimum buy size or changing fee rounding to avoid dropped small buys.

Additional technical notes (state transitions & access control)

- State transitions: `purchaseTokens` increases `tokenSupply_` and `tokenBalanceLedger_[_customerAddress]`, updates `payoutsTo_` to prevent new tokens from receiving past dividends, and sends fee portions to `profitPerShare_` and `dividendBalance_` via `allocateFees`.
- `sell` decreases `tokenSupply_` and `tokenBalanceLedger_`, adjusts `payoutsTo_` to reflect removed shares and allocates the fee split via `allocateFees`.
- `reinvest` and `withdraw` both mark dividends as paid by increasing `payoutsTo_` by `_dividends * magnitude` (cast to `int256`) and then either call `purchaseTokens` (reinvest) or transfer tokens out of contract (withdraw).
- Access control: There is no owner/manager role for token economics functions; buy/sell/reinvest/withdraw/transfer are public, gated only by token balances (`onlyBagholders`) or having dividends (`onlyStronghands`). `donatePool` relies on `transferFrom` allowances.
- Trust boundaries: The contract trusts the external `Token` ERC20 implementation for `transferFrom`, `transfer`, and `balanceOf`. Misbehaving token (non-standard ERC20) could break accounting.

I consider the three findings above sufficient for a first-pass high-priority remediation. I can draft suggested code patches (safe-cast helpers, buyPrice fix, min-buy guard) if you want.
