Checked files
- `stack_wbnb.sol` — full contract and SafeMath library
- `proxy_wbnb.sol` — proxy wrapper around the stack contract

What I inspected
- Constructors and initialization of `tokenAddress` / `stackAddress`
- Public variables and whether they can be changed
- Modifiers: `onlyBagholders`, `onlyStronghands`
- Cross-contract token flows between proxy and stack (approve/transferFrom)
- Dividend accounting: `profitPerShare_`, `payoutsTo_`, `dividendsOf`

Quick notes
- Modifiers enforce presence of tokens/dividends using `myTokens()` / `myDividends()`.
- Constructors set addresses but do not validate non-zero addresses.
- Proxy/stack flow: proxy pulls tokens from user, approves stack, calls `stack.buy` then transfers internal stack tokens to the user.
- Found a few validation/usability issues (see findings).

