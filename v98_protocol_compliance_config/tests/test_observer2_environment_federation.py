from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keddeh_observer2_environment_federation import EnvironmentFederation, FilesystemProcessProbe, MappingProbe
from keddeh_observer2_runtime import Observer2Runtime, ObserverIdentity, ObserverScope


class Observer2EnvironmentFederationTests(unittest.TestCase):
    def test_federation_composes_distinct_environment_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_file = Path(td) / "state.txt"
            state_file.write_text("A", encoding="utf-8")
            federation = EnvironmentFederation(
                "FEDERATION://TEST",
                [
                    FilesystemProcessProbe("ENV://RUNTIME", td, ("state.txt",), ()),
                    MappingProbe("ENV://REPOSITORY", {"branch": "candidate", "head": "abc"}),
                ],
            )
            first = federation.sample()
            state_file.write_text("B", encoding="utf-8")
            second = federation.sample()
            self.assertEqual([row["probe_id"] for row in first["environments"]], ["ENV://REPOSITORY", "ENV://RUNTIME"])
            self.assertNotEqual(first["federation_root"], second["federation_root"])

    def test_observer2_consumes_federation_as_live_sampling_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            federation = EnvironmentFederation(
                "FEDERATION://TEST",
                [MappingProbe("ENV://REPOSITORY", {"branch": "candidate", "head": "abc"})],
            )
            observer = Observer2Runtime(
                ObserverIdentity("OBSERVER2://TEST", "SITUATED_ENVIRONMENT_OBSERVER", "runtime-governor"),
                ObserverScope(td, (), ()),
                federation=federation,
            )
            frame = observer.sample(label="FEDERATED")
            self.assertEqual(frame["environment"]["sampling_mode"], "LIVE_FEDERATED_INTERROGATION")
            self.assertEqual(frame["observed_state"]["federation"]["federation_id"], "FEDERATION://TEST")

    def test_observer_has_no_mutation_api(self) -> None:
        self.assertFalse(hasattr(Observer2Runtime, "write"))
        self.assertFalse(hasattr(Observer2Runtime, "mutate"))
        self.assertFalse(hasattr(Observer2Runtime, "promote"))


if __name__ == "__main__":
    unittest.main()
