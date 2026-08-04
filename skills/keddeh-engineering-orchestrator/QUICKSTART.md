# KEO Five-Minute Quickstart

## Requirements

- Python 3.10 or newer.
- No third-party Python packages.
- No API key.
- No hosted account.
- No source upload.

## 1. List the available starter profiles

```bash
python3 keo.py profiles
```

Expected profiles:

```text
server
bios-firmware
hardware-abstraction
```

## 2. Initialise a project

### Server

```bash
python3 keo.py init ./demo-server \
  --name "KEDDEH Demo Server" \
  --profile server
```

### BIOS or firmware

```bash
python3 keo.py init ./demo-firmware \
  --name "KEDDEH Demo Firmware" \
  --profile bios-firmware
```

### Hardware abstraction

```bash
python3 keo.py init ./demo-hal \
  --name "KEDDEH Demo Hardware Abstraction" \
  --profile hardware-abstraction
```

## 3. Validate the project

```bash
python3 keo.py validate ./demo-server
```

Expected result:

```json
{
  "status": "PASS",
  "errors": []
}
```

## 4. Inspect the topology and product state

```bash
python3 keo.py inspect ./demo-server
```

The inspection reports the system identity, engineering profile, topology node and edge counts, interfaces, iteration state, promotion state, and privacy mode.

## Generated files

```text
keo.project.json   Product/project identity and privacy boundary
kir.json           Canonical KEDDEH Intermediate Representation
 topology.json      Software and execution topology
iteration.json     Current engineering iteration and remaining gates
PRODUCT_STATE.md   Human-readable state authority
README.md          Project-local onboarding
```

## First real iteration

After initialisation:

1. assign owners to topology nodes;
2. complete state and data planes in `kir.json`;
3. define interfaces and failure semantics;
4. add ADRs for material decisions;
5. implement the target source projection;
6. attach compile, synthesis, simulation, or runtime evidence;
7. run `keo validate` after every topology mutation;
8. promote only after bilateral readback.

## Privacy default

KEO operates locally and does not upload source code. Any future connector or managed-control-plane integration must be explicitly enabled and separately scoped.
