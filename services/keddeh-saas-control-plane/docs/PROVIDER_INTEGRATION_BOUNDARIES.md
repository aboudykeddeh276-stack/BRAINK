# Provider Integration Boundaries

The core control plane does not claim live Stripe, PayPal, Afterpay, Google Pay, Supabase, DNS, TLS, or public ingress execution.

Provider adapters must independently prove:
1. credential custody and secret isolation;
2. signed/provider-verifiable event validation;
3. replay protection and idempotency;
4. mapping into the core payment/identity/storage contract;
5. readback from provider and local state;
6. failure receipts without silent promotion.

The core accepts only already-verified provider events. A provider-specific adapter is responsible for proving that verification occurred.
