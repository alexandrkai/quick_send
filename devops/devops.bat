docker run -d `
  --restart always `
  --network app-network `
  --name redis `
  -p 6379:6379 `
  redis:8-alpine `
  redis-server --requirepass 291297 --appendonly yes