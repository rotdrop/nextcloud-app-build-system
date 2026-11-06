import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASE_STUB = r"""<?php
namespace OCP\App {
  interface IAppManager {
    function getAppInfoByPath($path);
    function isEnabledForAnyone($appId);
  }
}
namespace OCP {
  class Server {
    public static $services = [];
    public static function get($class) { return self::$services[ltrim($class, '\\')]; }
  }
}
namespace OC\AppFramework\Bootstrap {
%s
}
namespace {
  class OC {
    public static $CLI = true;
    public static $configDir;
  }
  OC::$configDir = __DIR__ . '/../config/';
  // like Nextcloud: simplexml_load_file() fails afterwards
  libxml_set_external_entity_loader(fn() => null);
  $manager = new class implements OCP\App\IAppManager {
    function getAppInfoByPath($path) { return ['id' => 'demo', 'namespace' => 'Demo']; }
    function isEnabledForAnyone($appId) { return %s; }
    function registerAutoloading($id, $path) { echo "autoload $id $path\n"; }
  };
  OCP\Server::$services[OCP\App\IAppManager::class] = $manager;
  if (class_exists('OC\AppFramework\Bootstrap\Coordinator')) {
    OCP\Server::$services['OC\AppFramework\Bootstrap\Coordinator'] = new OC\AppFramework\Bootstrap\Coordinator;
  }
}
"""

COORDINATOR = 'class Coordinator { function runLazyRegistration($id) { echo "lazy $id\\n"; } }'


class ConsoleSetupRegistrationTest(unittest.TestCase):
    """A mounted app which is not enabled is registered like a lazily loaded app."""

    def run_script(self, coordinator, enabled):
        with tempfile.TemporaryDirectory() as tmp:
            server = Path(tmp, "server")
            app = server / "apps/demo"
            (server / "lib").mkdir(parents=True)
            (server / "config").mkdir()
            (server / "config/config.php").write_text("<?php\n")
            (server / "lib/versioncheck.php").write_text("<?php\n")
            (server / "lib/base.php").write_text(BASE_STUB % (coordinator, enabled))
            (app / "appinfo").mkdir(parents=True)
            (app / "appinfo/info.xml").write_text("<info><id>demo</id><namespace>Demo</namespace></info>")
            (app / "dev-scripts/lib/scripts").mkdir(parents=True)
            (app / "dev-scripts/lib/scripts/console-setup.php").write_text(
                (ROOT / "scripts/console-setup.php").read_text())
            (app / "run.php").write_text(
                "<?php\n$argv = ['x', '--no-warnings'];\n"
                "define('ROT_DROP_DEV_SCRIPTS_APP_DIR', __DIR__);\n"
                "require __DIR__ . '/dev-scripts/lib/scripts/console-setup.php';\n"
                "echo \"done\\n\";\n")
            res = subprocess.run(["php", "-d", "xdebug.mode=off", str(app / "run.php")],
                                 capture_output=True, text=True, cwd=app)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertIn("done", res.stdout)
            return res.stdout, str(app.resolve())

    def test_lazy_registration_of_a_disabled_app(self):
        out, _ = self.run_script(COORDINATOR, "false")
        self.assertIn("lazy demo", out)

    def test_enabled_app_is_left_alone(self):
        out, _ = self.run_script(COORDINATOR, "true")
        self.assertNotIn("lazy", out)
        self.assertNotIn("autoload", out)

    def test_falls_back_to_the_autoloader_registration(self):
        out, app = self.run_script("class Other {}", "false")
        self.assertNotIn("lazy", out)
        self.assertIn("autoload demo " + app, out)


if __name__ == "__main__":
    unittest.main()
