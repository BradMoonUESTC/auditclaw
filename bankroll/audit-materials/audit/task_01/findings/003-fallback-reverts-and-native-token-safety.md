Title: Fallback function rejects native token transfers (intended) — confirms safe behavior

Severity: Informational

Affected files / functions
- `proxy_wbnb.sol`: fallback `function() payable public { require(false); }`
- `stack_wbnb.sol`: fallback `function() payable public { require(false); }`

Description
- Both proxy and stack implement a fallback payable function that immediately reverts via `require(false)`. This prevents accidental ERC20-wrapped native token (BNB/ETH) from being held by the contracts.

Impact
- Positive: prevents accidental locking of native currency. Any direct native transfers will revert.
- Consideration: contracts cannot accept native tokens even intentionally. If design later requires accepting native tokens, this will need to be changed.

Recommendation
- No action required for current design. Document the behavior clearly in interfaces so integrators don't attempt to send native tokens.

