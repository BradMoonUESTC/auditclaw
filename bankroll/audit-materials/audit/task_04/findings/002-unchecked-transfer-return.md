Title: `withdraw()` updates state without checking `token.transfer` return

Severity: Medium

Files / functions:
- `stack_wbnb.sol` — `withdraw()` (line ~268)

Description / root cause:
The `withdraw()` function computes `_dividends`, updates `payoutsTo_[_customerAddress]` to mark the dividends as paid, and then calls `token.transfer(_customerAddress, _dividends);` but does not check the boolean return value. The function proceeds to update `stats`, `totalTxs`, and `totalClaims` and emits events as if the transfer succeeded.

Impact / exploit scenario:
- If the token contract returns `false` on `transfer` (non-standard) or silently fails, the Stack contract will still record the withdrawal as completed even though tokens were not moved to the recipient. This leads to incorrect accounting and can permanently deprive users of tokens.
- Fee-on-transfer or deflationary tokens (which reduce the recipient amount) will also cause mismatches between expected and actual balances; the contract assumes full transfer succeeded.

Proof / code references:
- `stack_wbnb.sol::withdraw`:
  - updates `payoutsTo_[_customerAddress] += _dividends * magnitude;`
  - calls `token.transfer(_customerAddress,_dividends);` without `require`
  - then increments `stats[_customerAddress].withdrawn`, `totalTxs`, and `totalClaims`

Remediation suggestion:
- Check the return value and revert on failure: `require(token.transfer(_customerAddress, _dividends));`.
- Prefer using OpenZeppelin's `SafeERC20.safeTransfer` which handles tokens that do not return a boolean and reverts on failure.
- Consider validating resulting contract token balances (spot checks) or adopting a pull pattern where transfers are explicitly pulled by recipients with clear success checks.

