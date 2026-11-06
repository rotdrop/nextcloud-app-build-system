<?php
/**
 * Some PHP utility functions for Nextcloud apps.
 *
 * @author Claus-Justus Heine <himself@claus-justus-heine.de>
 * @copyright 2026 Claus-Justus Heine <himself@claus-justus-heine.de>
 * @license AGPL-3.0-or-later
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as
 * published by the Free Software Foundation, either version 3 of the
 * License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program. If not, see <http://www.gnu.org/licenses/>.
 */

// phpcs:disable PSR1.Files.SideEffects

/*-****************************************************************************
 *
 * Inject NC app setup
 *
 */

$coreFolder = ROT_DROP_DEV_SCRIPTS_APP_DIR . '/../..';

require_once $coreFolder . '/lib/versioncheck.php';

// use OC\Console\Application;

define('OC_CONSOLE', 1);

/**
 * @param Throwable $exception
 *
 * @return void
 *
 * @SuppressWarnings(PHPMD.ExitExpression)
 */
function exceptionHandler(Throwable $exception):void
{
  echo "An unhandled exception has been thrown:" . PHP_EOL;
  echo $exception;
  exit(1);
}
try {
  require_once $coreFolder . '/lib/base.php';

  // set to run indefinitely if needed
  if (strpos(@ini_get('disable_functions'), 'set_time_limit') === false) {
    @set_time_limit(0);
  }

  if (!OC::$CLI) {
    echo "This script can be run from the command line only" . PHP_EOL;
    exit(1);
  }

  set_exception_handler('exceptionHandler');

  if (!function_exists('posix_getuid')) {
    echo "The posix extensions are required - see http://php.net/manual/en/book.posix.php" . PHP_EOL;
    exit(1);
  }
  $user = posix_getpwuid(posix_getuid());
  $configUser = posix_getpwuid(fileowner(OC::$configDir . 'config.php'));
  if ($user['name'] !== $configUser['name']) {
    echo "Console has to be executed with the user that owns the file config/config.php" . PHP_EOL;
    echo "Current user: " . $user['name'] . PHP_EOL;
    echo "Owner of config.php: " . $configUser['name'] . PHP_EOL;
    echo "Try adding 'sudo -u " . $configUser['name'] . " ' to the beginning of the command (without the single quotes)" . PHP_EOL;
    echo "If running with 'docker exec' try adding the option '-u " . $configUser['name'] . "' to the docker command (without the single quotes)" . PHP_EOL;
    exit(1);
  }

  $appRoot = realpath(__DIR__ . '/../../../');

  $oldWorkingDir = getcwd();
  if ($oldWorkingDir === false) {
    echo "This script can be run from the app's root directory only." . PHP_EOL;
    echo "Can't determine current working dir - the script will continue to work but be aware of the above fact." . PHP_EOL;
  } elseif (realpath($oldWorkingDir) !== $appRoot && !chdir($appRoot)) {
    echo "This script can be run from the app's root directory only." . PHP_EOL;
    echo "Can't change to the app's root directory." . PHP_EOL;
    exit(1);
  }

  if (!function_exists('pcntl_signal') && !in_array('--no-warnings', $argv)) {
    echo "The process control (PCNTL) extensions are required in case you want to interrupt long running commands - see http://php.net/manual/en/book.pcntl.php" . PHP_EOL;
  }

  // Nextcloud only sets up the autoloading of enabled apps. A build
  // checkout mounted into a fresh server tree (e.g. in CI) is not enabled,
  // so register its namespace here; this is a no-op for enabled apps.
  $appInfoFile = $appRoot . '/appinfo/info.xml';
  $appInfo = is_file($appInfoFile) ? simplexml_load_file($appInfoFile) : false;
  if ($appInfo !== false && !empty((string)$appInfo->id) && !empty((string)$appInfo->namespace)) {
    $appId = (string)$appInfo->id;
    $appNamespace = 'OCA\\' . (string)$appInfo->namespace;
    $appManager = \OCP\Server::get(\OCP\App\IAppManager::class);
    if (method_exists($appManager, 'registerAutoloading')) {
      $appManager->registerAutoloading($appId, $appRoot);
    } elseif (is_dir($appRoot . '/lib')) {
      \OC::$server->registerNamespace($appId, $appNamespace);
      \OC::$composerAutoloader->addPsr4($appNamespace . '\\', $appRoot . '/lib/', true);
    }
  }

  // $application = \OCP\Server::get(Application::class);
} catch (Exception $ex) {
  exceptionHandler($ex);
} catch (Error $ex) {
  exceptionHandler($ex);
} catch (Throwable $ex) {
  exceptionHandler($ex);
}
