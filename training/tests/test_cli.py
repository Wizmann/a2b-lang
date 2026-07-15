import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from training.cli import main


class DatasetCliTests(unittest.TestCase):
    def test_generate_audit_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact = Path(temporary) / "dataset_smoke"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(
                        [
                            "dataset-generate",
                            "--seed",
                            "20260715",
                            "--output",
                            str(artifact),
                        ]
                    ),
                    0,
                )
                self.assertEqual(
                    main(["dataset-audit", "--artifact-dir", str(artifact)]),
                    0,
                )
                self.assertEqual(
                    main(
                        [
                            "dataset-report",
                            "--artifact-dir",
                            str(artifact),
                            "--passed",
                            "1",
                            "--duration",
                            "test",
                        ]
                    ),
                    0,
                )
            self.assertTrue((artifact / "REPORT.md").exists())


if __name__ == "__main__":
    unittest.main()
