import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("conflicts", ROOT / "scripts" / "conflicts.py")
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


class ConflictTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        for f in ("papers.json", "claims.json"):
            shutil.copy(ROOT / "tests" / "fixtures" / f, self.out / f)

    def tearDown(self):
        self.tmp.cleanup()

    def test_all(self):
        cf.main(["all", "--out", str(self.out)])  # returns normally on success
        for f in ("conflicts.json", "conflicts.md", "conflict_map.html", "claims.ttl"):
            self.assertTrue((self.out / f).exists(), f)
        res = json.loads((self.out / "conflicts.json").read_text())
        pairs = {(p["a"], p["b"]): p for p in res["pairs"]}
        # "B outperforms MA" is aligned with "A outperforms B": opposite conclusions, same dataset → genuine
        p12 = pairs.get(("C001", "C002")) or pairs.get(("C002", "C001"))
        self.assertEqual(p12["kind"], "contradiction")
        self.assertTrue(p12["genuine"])
        # null on a different dataset → explained, not genuine
        p13 = pairs.get(("C001", "C003")) or pairs.get(("C003", "C001"))
        self.assertEqual(p13["kind"], "null-vs-effect")
        self.assertFalse(p13["genuine"])
        self.assertIn("dataset", p13["differences"])
        # "training cost" and "training costs" fold together; effects 2 vs 8 → magnitude
        p45 = pairs.get(("C004", "C005")) or pairs.get(("C005", "C004"))
        self.assertEqual(p45["kind"], "magnitude")

    def test_plural_fold_keeps_words_intact(self):
        self.assertEqual(cf.plural_fold("continuous analysis networks studies"), "continuous analysis network study")

    def test_check_rejects_long_quote(self):
        cl = json.loads((self.out / "claims.json").read_text())
        cl["claims"][0]["quote"] = " ".join(["word"] * 30)
        (self.out / "claims.json").write_text(json.dumps(cl))
        with self.assertRaises(SystemExit) as e:
            cf.main(["check", "--out", str(self.out)])
        self.assertEqual(e.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
