
Checked files:
- `stack_wbnb.sol` (full contract and `SafeMath` library)

Focused areas:
- Dividend/accounting: `profitPerShare_`, `payoutsTo_`, `dividendBalance_`, `allocateFees`, `distribute`, `dividendsOf`, `dailyEstimate`.
- Token supply and balances: `tokenSupply_`, `tokenBalanceLedger_`, `purchaseTokens`, `sell`, `transfer`, `withdraw`, `reinvest`.
- Timing and drip configuration: `distributionInterval`, `balanceInterval`, `payoutRate_`, `lastPayout`, `lastBalance_`.

Reconstructed behaviour (state transitions & accounting):
- Tokens are minted on `purchaseTokens` by increasing `tokenSupply_` and the buyer's `tokenBalanceLedger_` by `_amountOfTokens = incoming - entryFee`.
- Fees (_undividedDividends) are passed to `allocateFees`, which: 1) pays 1/5 instantly by increasing `profitPerShare_` (per-share accumulator) and 2) adds 4/5 to `dividendBalance_` (the drip pool).
- `profitPerShare_` is an unsigned `uint256` representing cumulative profit-per-share scaled by `magnitude`.
- Per-account `payoutsTo_` is a signed `int256` used to track how much a user has already been credited; dividends are computed as `(profitPerShare_ * balance - payoutsTo_) / magnitude` with cast shims between unsigned/signed types.
- `distribute` is called after public actions. When enough time has passed (`now - lastPayout > distributionInterval`) and `tokenSupply_ > 0`, it computes a per-second share from `dividendBalance_` (based on `payoutRate_`), multiplies by elapsed seconds to get `profit`, subtracts `profit` from `dividendBalance_`, and increases `profitPerShare_` by `(profit * magnitude) / tokenSupply_`.

Trust boundaries & access control:
- All state changes are triggered by public functions; there is no privileged owner account in this contract. Anyone can call `distribute()` indirectly via flows that call it (e.g., `buy`, `sell`, `withdraw`, `reinvest`).
- Token transfers into the contract rely on an external `Token` ERC20 and `transferFrom` permissions — trust in ERC20 correctness.

Edge cases and arithmetic hazards observed:
- Signed/unsigned casts: casting `profitPerShare_ * balance` (uint256) to `int256` risks overflow if the unsigned value exceeds int256 max — this is already captured in findings.
- `dividendBalance_.safeSub(profit)` silently clamps to zero; `profitPerShare_` is still increased by the (possibly larger) `profit` value, enabling distribution of more dividends than existed.
- Very small `tokenSupply_` with a nonzero `dividendBalance_` can cause `(profit * magnitude) / tokenSupply_` to be huge, magnifying `profitPerShare_`.
- `distributionInterval` is set to `2 seconds` while `payoutRate_` is `2` (%) per day; the per-second share computation divides by `24 hours` (seconds in day) and multiplies by elapsed seconds — be mindful of small rounding/precision effects.

Follow-ups already created as findings:
- `findings/01-signed-unsigned-dividend.md` (High): signed/unsigned conversion risk in `dividendsOf` and `payoutsTo_` updates.
- `findings/02-dividendbalance-underflow.md` (Medium): `dividendBalance_` clamping allows distributing more than available.

Suggested tests to add:
- Fuzz `profitPerShare_ * balance` growth to check int256 cast limits.
- Simulate `dividendBalance_` smaller than computed `profit` to validate that `profitPerShare_` updates do not exceed available funds.
- Edge-case: single holder with tiny `tokenSupply_` receiving large `dividendBalance_` and successive `distribute` calls.

