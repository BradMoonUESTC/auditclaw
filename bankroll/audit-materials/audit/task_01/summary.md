Scope
- Files reviewed: `proxy_wbnb.sol`, `stack_wbnb.sol`
- Target functions: `BankrollNetworkStackProxy.donatePool`, `.buyFor`, `.buy`, and fallback

Summary
- I reconstructed token flows between user -> proxy -> stack.
- Found issues around allowance handling and residual token capture patterns in the proxy.
- Found compatibility risks with non-standard ERC20 tokens (no return, fee-on-transfer).
- Fallback correctly reverts to prevent native token retention.

Status
- Findings created for concrete issues. See `findings/` for details.

