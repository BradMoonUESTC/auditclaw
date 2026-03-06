# 01 - Missing constructor validation (zero address)

Severity: Medium

Affected files
- `stack_wbnb.sol` — `constructor(address _tokenAddress)`
- `proxy_wbnb.sol` — `constructor(address _tokenAddress, address _stackAddress)`

Description / root cause
- Both contracts assign incoming addresses to `tokenAddress` and `stackAddress` (proxy) or `tokenAddress` (stack) without checking for the zero address. If deployed with a zero address or a mistakenly set address, the contract may be initialized with an invalid token reference. The `stack` contract stores `token = Token(_tokenAddress)` and will call `token.transfer` / `transferFrom` on that interface — if `tokenAddress` is zero, calls will target address(0) and revert, potentially locking functionality. The proxy similarly sets `stack = BankrollNetworkStack(_stackAddress)` without validating.

Exploit / impact
- If a constructor parameter is set to `0x0` (either by mistake or via malicious factory), essential token operations will fail (reverts on external calls) and the contract may be unusable. An attacker cannot change these addresses later, but users and deployers may accidentally deploy defective contracts. This is primarily a usability/availability risk.

Recommendation
- Add require checks in constructors: `require(_tokenAddress != address(0));` and `require(_stackAddress != address(0));` where applicable. Optionally emit an event documenting initialization.

