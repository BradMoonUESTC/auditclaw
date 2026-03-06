Scope
- Reviewed `stack_wbnb.sol` and `proxy_wbnb.sol` for access control, public state exposure, constructor initialization, and modifiers.

What I reviewed
- Modifiers: `onlyBagholders`, `onlyStronghands` — ensure callers own tokens / have dividends.
- Public fields: `tokenAddress`, `stackAddress`, `tokenSupply_`, balances exposed via `balanceOf` and `totalTokenBalance()`.
- Constructors in both contracts to check for zero-address and ownership assumptions.

Summary of findings
- I found concrete issues related to missing constructor validation and unsafe use of `approve`/`transferFrom` flows in the proxy that can lead to residual token capture and potential front-running or unexpected behavior. See findings in the `findings/` folder for details and remediation.

Conclusion
- The contracts implement basic modifiers to restrict operations to token-holders or dividend-holders; however there are validation gaps (missing zero-address checks) and economic/UX concerns around proxy token handling that can lead to user funds being unintentionally used during multi-tx interactions. These are medium-severity issues.

