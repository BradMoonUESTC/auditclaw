Checked files and areas:

- `stack_wbnb.sol` — focused on `purchaseTokens`, `allocateFees`, `distribute`, `buyPrice`, `sellPrice`, `calculateTokensReceived`, `calculateethReceived`, and casting/use of `profitPerShare_` and `payoutsTo_`.
- `audit-materials/decompose/tasks/task_02/task.json` — task scope and edge-cases.
- `audit-materials/request.md` — run metadata.

Quick notes and verification steps performed:
- Confirmed `entryFee_`/`exitFee_` constants are both `10` (10%); contract comments are stale (claiming different percentages).
- Verified `purchaseTokens` logic: fees are subtracted from incoming token amount, tokens minted = `_incomingeth - _incomingeth * entryFee_ / 100`.
- Confirmed `calculateTokensReceived` matches `purchaseTokens` behavior (both subtract fees).
- Confirmed `buyPrice()` is inconsistent (it adds the fee) and will mislead callers or frontends.
- Traced `allocateFees`: 1/5 of fee is distributed instantly via `profitPerShare_` (scaled by `magnitude`), 4/5 goes to `dividendBalance_` for drip.
- Traced `distribute`: periodically moves a time-proportional portion of `dividendBalance_` into `profitPerShare_` using `magnitude` scaling.
- Inspected casts to `int256` for `payoutsTo_` updates in `purchaseTokens`, `sell`, `reinvest`, `withdraw`, `transfer` and confirmed unsafe direct casts without bounds checks.
- Checked initial purchase branch (`tokenSupply_ == 0`) — tokens equal to net paid amount; no special privileged behavior but initial buyer receives full tokenSupply_.

Files created/updated in this task folder:
- `memory.md` (this file)
- `summary.md`
- `findings/01-buyprice-incorrect.md`
- `findings/02-unsafe-int-cast-overflow.md`
- `findings/03-small-buys-zero-tokens.md`
