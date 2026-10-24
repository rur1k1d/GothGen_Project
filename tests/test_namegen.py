import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import namegen


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = namegen.load_names()
        cls.lexicon = namegen.load_lexicon()

    def test_data_has_entries(self):
        self.assertGreaterEqual(len(self.entries), 60)

    def test_ids_are_unique(self):
        ids = [entry.id for entry in self.entries]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_entry_has_source(self):
        missing = [entry.id for entry in self.entries if not entry.source]
        self.assertEqual(missing, [])

    def test_required_cultures_present(self):
        cultures = {entry.culture for entry in self.entries}
        for culture in [
            "gothic",
            "geat",
            "anglo_saxon",
            "norse",
            "varangian_rus",
            "scythian",
            "alan_sarmatian",
        ]:
            self.assertIn(culture, cultures)

    def test_goar_is_alanic_not_gothic(self):
        goar = namegen.find_entry(self.entries, "Goar")
        self.assertEqual(goar.culture, "alan_sarmatian")
        self.assertTrue(goar.gothic_like)

    def test_lexicon_has_elements(self):
        self.assertGreaterEqual(len(self.lexicon), 20)


class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = namegen.load_names()
        cls.lexicon = namegen.load_lexicon()

    def test_daily_is_deterministic(self):
        first = namegen.daily_entries(self.entries, "2026-10-22", top=3)
        second = namegen.daily_entries(self.entries, "2026-10-22", top=3)
        self.assertEqual([entry.id for entry in first], [entry.id for entry in second])

    def test_daily_respects_culture(self):
        picks = namegen.daily_entries(self.entries, "2026-10-22", culture="gothic", top=5)
        self.assertTrue(all(entry.culture == "gothic" for entry in picks))

    def test_generate_is_seeded(self):
        first = namegen.generate_entries(self.entries, count=8, seed=42)
        second = namegen.generate_entries(self.entries, count=8, seed=42)
        self.assertEqual([entry.id for entry in first], [entry.id for entry in second])
        self.assertEqual(len({entry.id for entry in first}), 8)

    def test_generate_respects_gender(self):
        picks = namegen.generate_entries(self.entries, gender="f", count=5, seed=7)
        self.assertTrue(all(entry.gender == "f" for entry in picks))

    def test_places_are_excluded_by_default(self):
        picks = namegen.generate_entries(self.entries, culture="anglo_saxon", count=20, seed=1)
        self.assertNotIn("heorot", {entry.id for entry in picks})

    def test_filter_excludes_places(self):
        filtered = namegen.filter_entries(self.entries, culture="anglo_saxon")
        self.assertNotIn("heorot", {entry.id for entry in filtered})

    def test_combine_gothic(self):
        results = namegen.combine_entries(self.lexicon, "gothic", count=4, seed=3)
        self.assertEqual(len(results), 4)
        self.assertTrue(all(item["status"] == "constructed" for item in results))

    def test_combine_rejects_scythian(self):
        with self.assertRaises(ValueError):
            namegen.combine_entries(self.lexicon, "scythian", count=1)

    def test_unknown_name_raises(self):
        with self.assertRaises(KeyError):
            namegen.find_entry(self.entries, "NotARealName")


class TextTests(unittest.TestCase):
    def test_leetspeak(self):
        self.assertEqual(namegen.leetspeak("Alaric"), "4L4R1C")
        self.assertEqual(namegen.leetspeak("Beowulf"), "B30WULF")

    def test_ascii_fold(self):
        self.assertEqual(namegen.ascii_fold("Þórr"), "Thorr")
        self.assertEqual(namegen.ascii_fold("Æthelred"), "AEthelred")

    def test_format_entry_includes_safety_line(self):
        entry = namegen.find_entry(namegen.load_names(), "Wiglaf")
        text = namegen.format_entry(entry)
        self.assertIn("Check domain and trademark availability", text)

    def test_json_is_valid(self):
        entry = namegen.find_entry(namegen.load_names(), "Rurik")
        payload = json.loads(namegen.entry_to_json(entry))
        self.assertEqual(payload["name"], "Rurik")
        self.assertEqual(payload["leet"], "RUR1K")


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "namegen.py"), *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_leet_cli(self):
        result = self.run_cli("leet", "Teia")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("7314", result.stdout)

    def test_offer_cli(self):
        result = self.run_cli("offer", "Alaric")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Brand directions", result.stdout)

    def test_explain_json_cli(self):
        result = self.run_cli("explain", "Goar", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["culture"], "alan_sarmatian")

    def test_daily_cli(self):
        result = self.run_cli("daily", "--date", "2026-10-22", "--top", "2")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Name:"), 2)

    def test_combine_scythian_cli_errors(self):
        result = self.run_cli("combine", "--culture", "scythian")
        self.assertEqual(result.returncode, 2)
        self.assertIn("attested-only", result.stderr)


if __name__ == "__main__":
    unittest.main()
