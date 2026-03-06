Title: Unchecked ERC20 `transfer` return in `withdraw()`

Severity: High

Affected files/functions:
- `stack_wbnb.sol::withdraw()`

Root cause

`withdraw()` computes the caller's dividends, updates `payoutsTo_` (so the caller is marked as paid), and then calls `token.transfer(_customerAddress, _dividends);` without checking the boolean return value. The code then updates stats and emits events as if the transfer succeeded.

Why this is a problem

- Not all ERC20 tokens return a boolean from `transfer` (or may return false on failure). If `token.transfer` silently fails (returns false) or behaves non-standardly, the contract will have already updated internal accounting marking the user as paid while the ERC20 tokens remain in the contract, effectively stealing the user's dividends.
- If the token reverts on failure, `withdraw()` will revert before internal accounting is updated — this is safe. The issue is with tokens that return `false` on failure but do not revert. In this case the user loses funds (internal state says paid) while tokens are not transferred.

Impact / exploit scenario

- A malicious or non-standard ERC20 could return `false` on `transfer` under certain conditions (e.g., blacklisting, insufficient balance due to fee-on-transfer), causing users to be marked as paid when they did not receive tokens.

Remediation

- Check the return value of ERC20 `transfer` and revert on failure: `require(token.transfer(...), "transfer failed");`.
- For maximum compatibility, adopt OpenZeppelin's `SafeERC20` wrappers which handle tokens that do not return a value by checking for success via low-level call and revert on failure.

