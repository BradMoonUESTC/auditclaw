# Solidity Audit Checklist

- Access control on privileged functions and upgrade hooks
- Value/accounting consistency between wrappers and underlying contracts
- Reentrancy opportunities around external calls and token transfers
- Missing validation for user-supplied addresses or amounts
- Inconsistent bookkeeping across mirrored entrypoints
- Edge cases around zero values, self-referrals, and repeated actions
- Event emission consistency for state-changing flows
- Dangerous assumptions about token behavior, decimals, or approvals
