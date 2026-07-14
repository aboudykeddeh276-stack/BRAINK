# KEX-BRAINK Bilateral Polygon Active Skill v1

## Activation

Use this skill whenever work concerns KEX, BRAINK, bilateral learning, polygon bias, theorem development, artifact verification, runtime adaptation, or recursive project improvement. This is an execution skill, not a reporting template.

## Governing loop

`anchor -> factor -> translate -> act -> validate -> tokenize -> preserve -> return`

## Six-axis polygon

```text
P = (
  anchor_fidelity,
  factor_completeness,
  translation_fidelity,
  action_execution,
  validation_strength,
  preservation_continuity
)
```

Each axis is scored from explicit predicates:

`axis_score = passed_predicates / total_predicates`

`polygon_average = sum(axis_scores) / 6`

Preserved baseline:

`baseline = 0.8166666666666668`

Pass condition:

```text
polygon_average >= baseline - tolerance
AND every critical predicate passes
AND neutral/uniform input remains neutral/uniform
```

## Route-scoped bounded learning

```text
b_(t+1,i) = clamp(
  (1-decay)*b_(t,i) + learning_rate*(score_i-baseline),
  -bias_bound,
  +bias_bound
)
```

A learning delta is valid only when it contains:

```text
source_artifact
manifest_token
checker_route
evidence_class
boundary
next_route
```

Neutral uniform inputs bypass learned bias. Bias is inspectable route state, not a hidden global personality change.

## Bilateral readback

`coverage = satisfied_required_outputs / required_outputs`

`residual = 1 - coverage`

A nonzero residual becomes a blocker or next route; it is never hidden as completion.

## Action-first rule

```text
artifact_first = true
report_after_action = true
report_only = invalid when executable action is available
```

## Preservation

Every run must retain its directive packet, source anchors, polygon predicates and scores, action receipts, tests, bilateral readback, route state, blocker state, rollback and continuation route.
