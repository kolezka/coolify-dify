import json
import os
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class FrontendNetworkTests(unittest.TestCase):
    def test_frontend_binds_all_interfaces_despite_host_hostname(self):
        environment = {**os.environ, "HOSTNAME": "docker-host-name"}
        result = subprocess.run(
            [
                "docker", "compose",
                "--file", str(ROOT / "docker-compose.yaml"),
                "--env-file", str(ROOT / ".env.example"),
                "config", "--format", "json",
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
        services = json.loads(result.stdout)["services"]
        self.assertEqual(
            services["web"]["environment"].get("HOSTNAME"),
            "0.0.0.0",
            "Next.js must listen on every interface, not a resolved container hostname",
        )
        self.assertEqual(
            [name for name, service in services.items()
             if "HOSTNAME" in service.get("environment", {})],
            ["web"],
            "The frontend bind override must not change other services' hostnames",
        )


class PluginDaemonStorageTests(unittest.TestCase):
    """plugin_daemon runs as uid 1001 and must be able to write its storage volume."""

    PROJECT = "dify-perm-test"

    def compose(self, *args, check=True):
        return subprocess.run(
            [
                "docker", "compose",
                "--project-name", self.PROJECT,
                "--file", str(ROOT / "docker-compose.yaml"),
                "--env-file", str(ROOT / ".env.example"),
                *args,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=check,
        )

    def docker(self, *args, check=True):
        return subprocess.run(["docker", *args], text=True, capture_output=True, check=check)

    def setUp(self):
        self.compose("down", "--volumes", check=False)
        self.addCleanup(self.compose, "down", "--volumes", check=False)

    def test_existing_install_gets_writable_plugin_storage(self):
        # An install made before this fix: app storage already initialized, plugin volume root-owned.
        self.compose("create", "--no-recreate", "init_permissions")
        app_volume = f"{self.PROJECT}_dify_app_storage"
        plugin_volume = f"{self.PROJECT}_dify_plugin_daemon"
        self.docker("volume", "create", plugin_volume)
        self.docker("run", "--rm", "-v", f"{app_volume}:/s", "busybox:latest",
                    "touch", "/s/.init_permissions")

        self.compose("run", "--rm", "--no-deps", "init_permissions")

        write = self.docker("run", "--rm", "--user", "1001:1001", "-v", f"{plugin_volume}:/app/storage",
                            "busybox:latest", "mkdir", "/app/storage/assets", check=False)
        self.assertEqual(write.returncode, 0, f"uid 1001 cannot write plugin storage: {write.stderr}")

    def test_plugin_daemon_waits_for_init_permissions(self):
        services = json.loads(self.compose("config", "--format", "json").stdout)["services"]
        dependency = services["plugin_daemon"].get("depends_on", {}).get("init_permissions", {})
        self.assertEqual(dependency.get("condition"), "service_completed_successfully")


if __name__ == "__main__":
    unittest.main()
