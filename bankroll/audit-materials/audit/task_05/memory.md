Checked files and quick notes

- Reviewed task file: `audit-materials/decompose/tasks/task_05/task.json` (access control, public variables, constructors)
- Primary contracts reviewed: `stack_wbnb.sol`, `proxy_wbnb.sol` at repo root
- Confirmed Solidity version `^0.4.25`
- No owner/administrator or upgrade mechanism present in either contract
- Proxy relays user token deposits into the Stack contract by:
  - pulling ERC20 tokens from the user to proxy (`token.transferFrom(msg.sender, proxy, amount)`)
  - approving the Stack contract to move the proxy's token balance (`token.approve(stackAddress, balance)`)
  - calling `stack.buy(balance)` which causes the Stack contract to `transferFrom(proxy, stack, balance)`
  - transferring internal Stack tokens from proxy to the target customer via `stack.transfer(customer, stack_balance)`
- Noted design choices: proxy intentionally consumes any residual ERC20 balance it holds when executing `buyFor`

