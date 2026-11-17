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


if __name__ == "__main__":
    unittest.main()
