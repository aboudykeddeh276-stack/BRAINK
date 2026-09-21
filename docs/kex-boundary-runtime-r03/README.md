# KEX Boundary Runtime R03

Self-hosted, dependency-free reference implementation for the IL-LLM -> KEX -> explicit substrate boundary.

Runtime dependency graph: none on GitHub. GitHub is distribution/version control only.

Layers: IL-LLM semantic identity -> KEX symbolic state -> coordinate/instance resolution -> target projection or binary boundary -> substrate bytes.

Run:
python3 -m unittest discover -s tests -v
python3 src/runtime_demo.py

Seed: KEX-BND-R03-20260921-7F2A91C4

The A/B codec is a canonical run representation over {0,1}. It is reversible for its declared domain; it is not claimed to compress every input or provide cryptographic security.

## BRAINK utility library extension: Waveform Geometry R03

ChatGPT/platform adapter utility surface now includes:
- WaveformGeometryEngine: deterministic torus embedding with 256 non-aliased phase bins.
- GeometricSignalModulator / GeometricDemodulator: geometry-to-wave-symbol and reverse boundary.
- GeometryBoundaryAdapter: SHA-256 + CRC integrity, 0.297 configured jitter admission bound.
- WaveformCoordinateDirectory: generation-fenced coordinate state.
- WaveformLayer2Reconciler: MATERIALISE / REPLACE / NOOP state reconciliation.
- Falsification tests: endpoint phase alias, manifold distortion, phase corruption, jitter overflow, generation replay and independent-node divergence.

Qualification boundary: local waveform suite observed 11/11 PASS. This library does not claim that non-zero toroidal norm alone makes distributed desynchronization impossible; independent nodes still require an agreement protocol and authenticated transport.
