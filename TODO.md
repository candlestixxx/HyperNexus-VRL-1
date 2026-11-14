# Granular Short-Term Tasks & To-Do List — HyperNexus VRL-1

## Immediate Tasks & Short-Term Enhancements

### Database & Persistence
- [ ] Add direct asyncpg (PostgreSQL) and motor (MongoDB) driver integrations to `MultiTenantDBPoolManager`.
- [ ] Add automated database migration runner on tenant onboarding.
- [ ] Implement automatic periodic archiving for tenant audit databases.

### Developer Portal UI
- [ ] Add CSV/JSON export button for tenant audit logs in the portal UI.
- [ ] Add interactive Canvas node dragging / rotation in the Radial Vector visualizer.
- [ ] Add dark/light mode toggle in developer portal header.

### Security & Governance
- [ ] Add API key rotation endpoint (`POST /api/v1/tenants/{id}/rotate-key`).
- [ ] Add IP CIDR whitelisting rules per tenant in `TenantContext`.
- [ ] Implement HMAC webhook signature generation for upstream forwarded payloads.

### CI/CD & Automation
- [ ] Add GitHub Actions CI workflow to run pytest and linters on push.
- [ ] Add Dependabot automated vulnerability scanning.
