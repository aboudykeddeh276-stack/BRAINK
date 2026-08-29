# V98 Application, Applet and Telemetry Abstraction Specification

## 1. Purpose of an application

An application is the deployable software product surface that gives a user an end-to-end capability. It is not only buttons or screens. It is the combined package of user interface, state, functions, runtime, persistence, permissions, observability and deployment rules.

In the KEDDEH workstation, an application is a bounded capability domain, such as the service spine dashboard, HEMOS runtime surface, mirror update lane, agent registry, or compliance console.

A user experiences an app as a coherent tool. A computer sees it as a process tree, data model, runtime context, event loop, module graph, permission envelope and persistence boundary.

## 2. Purpose of an applet

An applet is a smaller bounded capability embedded inside a larger application or workstation surface. It is not a whole product by itself. It is a focused tool cell with a narrow job and a host-controlled lifecycle.

Examples:

- service-status applet
- agent-registry applet
- ledger-readback applet
- mirror-lane applet
- virtual GPU frame-state applet
- target-host-gate applet

The host application controls the applet's permissions, state source, routing, telemetry and execution contract.

## 3. Telemetry within an application

Telemetry is observation data emitted by the application, runtime, framework, service, function, process or execution path. It does not perform the business action itself. It records what happened, where it happened, how long it took, what state changed, and whether an error or gate condition occurred.

The telemetry layer answers:

```text
What happened?
Where did it happen?
When did it happen?
How long did it take?
Which service/function/path emitted it?
What user-visible result did it affect?
What receipt or gate does it support?
```

Telemetry is not proof by itself. Telemetry supports diagnosis, audit, replay and user trust when joined to executed behavior, tests, ledger readback and receipts.

## 4. Telemetry versus functions

A function performs a defined computation or side effect. Telemetry observes and records that computation or side effect.

Example:

```text
function: write_ledger(entry)
telemetry: ledger_write_event{entry_hash, path, timestamp, result}
```

The function changes or produces state. Telemetry describes the function's behavior.

## 5. Telemetry versus buttons

A button is a user-interface trigger. It does not equal the operation itself. It emits an input event that may call a function, start a process, or request a runtime transition.

Example:

```text
button: Run Mirror Lane
function: run_mirror_lane(root)
process: Python execution and ledger write
telemetry: ui_click_event + mirror_lane_trace + receipt_write_log
```

The button initiates; the function executes; the process runs; telemetry observes.

## 6. Telemetry versus processes

A process is an operating-system execution unit. Telemetry records process state such as start, stop, exit code, memory, CPU, error output and log events.

A process can run without telemetry, but then failures become difficult to explain. A telemetry stream can observe a process, but it cannot replace the process.

## 7. Telemetry versus frameworks

A framework supplies reusable structure, conventions, APIs and lifecycle control. Telemetry records how framework-managed work behaves.

Example:

```text
framework: launchd service supervision
runtime: python3 executing acceptance harness
function: run_acceptance()
telemetry: service-start event, exit-code metric, ledger-readback log
```

The framework governs structure. Telemetry makes operation visible.

## 8. Telemetry versus runtimes

A runtime is the execution environment for code: Python, WebAssembly, browser, V86, Swift, Rust, shell, launchd or the self-hosted runner. Telemetry records runtime behavior and resource use.

The runtime executes. Telemetry observes.

## 9. Telemetry versus execution paths

An execution path is the actual route taken through code and services, for example:

```text
button_click -> run.command -> acceptance_harness -> service_receipts -> ledger -> outbox
```

Telemetry turns that path into traces, metrics and logs. A trace shows path; a metric measures quantity; a log records event detail.

## 10. KEDDEH operational convention

For every application and applet, the system must preserve this separation:

```text
UI element triggers.
Function computes.
Process hosts.
Framework structures.
Runtime executes.
Execution path connects.
Telemetry observes.
Ledger records.
Acceptance harness promotes.
```

No UI element, telemetry item, framework label or hash may substitute for executed behavior and acceptance receipts.
