# KEX Boundary Runtime R03

Self-hosted, dependency-free reference implementation for the IL-LLM -> KEX -> explicit substrate boundary.

Runtime dependency graph: none on GitHub. GitHub is distribution/version control only.

Layers: IL-LLM semantic identity -> KEX symbolic state -> coordinate/instance resolution -> target projection or binary boundary -> substrate bytes.

Run:
python3 -m unittest discover -s tests -v
python3 src/runtime_demo.py

Seed: KEX-BND-R03-20260921-7F2A91C4

The A/B codec is a canonical run representation over {0,1}. It is reversible for its declared domain; it is not claimed to compress every input or provide cryptographic security.