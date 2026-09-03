# Authorship, Accountability and Governance R16

Roles remain logically distinct: Author, Owner, Authority, Operator, Verifier, Administrator and Observer.

Every material mutation records: `receipt_id, unit_id, actor, authority, action, input_state, mutation, evidence, verification, result_state, rollback, status, timestamp, digest`.

If documentation says PASS but execution says FAIL, execution wins. If execution is unavailable, state is UNKNOWN/BLOCKED. If authorities conflict, the authored authority hierarchy resolves the conflict before mutation.

Accountability chain: `Request → Authority → Actor → Mutation → Evidence → Verification → Readback → Receipt → Owner`.

Anonymous administrative mutation is invalid. Authorship does not automatically imply deployment authority; ownership does not automatically imply authorship; observation does not automatically imply control authority.
