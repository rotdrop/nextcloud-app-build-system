import subprocess
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ScopedVendorTest(unittest.TestCase):
    def test_vendor_suffix_and_composer_patch(self):
        for namespace in ("Scoped", "Wrapped", "CuStOm"):
            with self.subTest(namespace=namespace), tempfile.TemporaryDirectory() as temporary:
                app = Path(temporary)
                suffix = namespace.lower()
                vendor = f"vendor-{suffix}"
                (app / "appinfo").mkdir()
                (app / "appinfo/info.xml").write_text(
                    f"<info><scopednamespace>{namespace}</scopednamespace></info>",
                )
                (app / f"composer-{suffix}.json").write_text("{}")
                autoload = app / vendor / "composer" / "autoload_real.php"
                autoload.parent.mkdir(parents=True)
                original = (
                    "            }\n"
                    "        }, null, null);\n"
                    "        foreach ($filesToLoad as $fileIdentifier => $file) {\n"
                    "            $requireFile($fileIdentifier, $file);\n"
                    "        }\n"
                    "\n"
                    "        return $loader;\n"
                )
                autoload.write_text("\n" * 46 + original)
                xpath = app / "xpath"
                xpath.write_text(
                    "#!/usr/bin/env python3\n"
                    "import sys, xml.etree.ElementTree as ET\n"
                    "root = ET.parse(sys.argv[-1]).getroot()\n"
                    "print(root.findtext('scopednamespace') "
                    "if sys.argv[-2] == '/info/scopednamespace/text()' else 'Test')\n",
                )
                xpath.chmod(0o755)
                (app / "Makefile").write_text(
                    f"ABSSRCDIR := {app}\n"
                    f"DEV_LIB_DIR := {ROOT}\n"
                    f"include {ROOT}/makefile/setup.mk\n"
                    f"include {ROOT}/makefile/l10n.mk\n"
                    "check:\n"
                    "\t@echo $(SCOPED_VENDOR_SUFFIX)\n"
                    "\t@echo $(TS_PHP_SOURCE_DIRS)\n"
                    "\t$(call apply-scoped-autoload-patch,vendor-$(SCOPED_VENDOR_SUFFIX))\n"
                )
                result = subprocess.run(
                    ["make", "--no-print-directory", "-C", str(app),
                     f"XPATH={xpath}", "check"],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(f"{suffix}\n", result.stdout)
                self.assertIn(
                    f"lib {vendor}/rotdrop/nextcloud-app-toolkit/src\n", result.stdout,
                )
                self.assertEqual(
                    autoload.read_text(),
                    ("\n" * 46 + original).replace(
                        "$requireFile($fileIdentifier, $file);",
                        f"$requireFile('OCA_Test_{namespace}' . $fileIdentifier, $file);",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
