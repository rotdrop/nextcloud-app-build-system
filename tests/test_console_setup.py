import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE_STUB = r"""<?php
namespace OCP\App { interface IAppManager {} }
namespace OCP {
  class Server {
    public static $manager;
    public static function get($class) { return self::$manager; }
  }
}
namespace {
  class OC {
    public static $CLI = true;
    public static $configDir;
    public static $composerAutoloader;
    public static $server;
  }
  OC::$configDir = __DIR__ . '/../config/';
  OC::$composerAutoloader = new class { public $psr4 = []; function addPsr4($ns, $dir, $prepend) { $this->psr4[$ns] = $dir; } };
  OC::$server = new class { public $ns = []; function registerNamespace($id, $ns) { $this->ns[$id] = $ns; } };
  OCP\Server::$manager = %s;
}
"""

MODERN = "new class implements OCP\\App\\IAppManager { function registerAutoloading($id, $path) { echo \"register $id $path\\n\"; } }"
LEGACY = "new class implements OCP\\App\\IAppManager {}"


class ConsoleSetupAutoloadTest(unittest.TestCase):
    """The app namespace is registered although the app is not enabled."""

    def run_script(self, manager):
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp, "server")
            app = server / "apps/demo"
            (server / "lib").mkdir(parents=True)
            (server / "config").mkdir()
            (server / "config/config.php").write_text("<?php\n")
            (server / "lib/versioncheck.php").write_text("<?php\n")
            (server / "lib/base.php").write_text(BASE_STUB % manager)
            (app / "appinfo").mkdir(parents=True)
            (app / "lib").mkdir()
            (app / "appinfo/info.xml").write_text(
                "<info><id>demo</id><namespace>Demo</namespace></info>")
            (app / "dev-scripts/lib/scripts").mkdir(parents=True)
            (app / "dev-scripts/lib/scripts/console-setup.php").write_text(
                (ROOT / "scripts/console-setup.php").read_text())
            (app / "run.php").write_text(
                "<?php\n$argv = ['x', '--no-warnings'];\n"
                "define('ROT_DROP_DEV_SCRIPTS_APP_DIR', __DIR__);\n"
                "require __DIR__ . '/dev-scripts/lib/scripts/console-setup.php';\n"
                "echo json_encode([OC::$composerAutoloader->psr4, OC::$server->ns]) . \"\\n\";\n")
            return subprocess.run(["php", "-d", "xdebug.mode=off", str(app / "run.php")],
                                  capture_output=True, text=True, cwd=app), str(app.resolve())

    def test_uses_the_app_manager(self):
        res, app = self.run_script(MODERN)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("register demo " + app, res.stdout)

    def test_falls_back_to_the_composer_autoloader(self):
        res, app = self.run_script(LEGACY)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn('"OCA\\\\Demo\\\\":"' + app.replace("/", "\\/") + '\\/lib\\/"', res.stdout)
        self.assertIn('"demo":"OCA\\\\Demo"', res.stdout)


if __name__ == "__main__":
    unittest.main()
