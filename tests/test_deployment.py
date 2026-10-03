import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigurationTests(unittest.TestCase):
    def test_server_image_builds_web_and_runs_migrations(self):
        dockerfile = (ROOT / 'server' / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('FROM node:22-alpine AS web-build', dockerfile)
        self.assertIn('npm run build', dockerfile)
        self.assertIn('COPY --from=web-build /web/dist /app/web/dist', dockerfile)
        self.assertIn('python migrate_database.py', dockerfile)
        self.assertIn('WEB_DIST_DIR=/app/web/dist', dockerfile)

    def test_compose_uses_repository_root_as_docker_context(self):
        compose = (ROOT / 'docker-compose.yml').read_text(encoding='utf-8')
        self.assertIn('context: .', compose)
        self.assertIn('dockerfile: server/Dockerfile', compose)

    def test_application_ci_and_windows_installer_workflows_exist(self):
        workflows = ROOT / '.github' / 'workflows'
        self.assertFalse((workflows / 'python-publish.yml').exists())
        ci = (workflows / 'ci.yml').read_text(encoding='utf-8')
        windows = (workflows / 'windows-installer.yml').read_text(encoding='utf-8')
        self.assertIn('python tests/postgres_smoke.py', ci)
        self.assertIn('python -m unittest discover -s tests -v', ci)
        self.assertIn('npm run build', ci)
        self.assertIn('npm run test:e2e', ci)
        self.assertIn('upgrade head', ci)
        self.assertIn('working-directory: server', ci)
        self.assertIn('PyInstaller', windows)
        self.assertIn('ISCC.exe', windows)


    def test_render_blueprint_uses_docker_health_and_external_secrets(self):
        blueprint = (ROOT / 'render.yaml').read_text(encoding='utf-8')
        self.assertIn('runtime: docker', blueprint)
        self.assertIn('dockerfilePath: ./server/Dockerfile', blueprint)
        self.assertIn('dockerContext: .', blueprint)
        self.assertIn('healthCheckPath: /api/health', blueprint)
        self.assertIn('key: DATABASE_URL', blueprint)
        self.assertIn('sync: false', blueprint)



if __name__ == '__main__':
    unittest.main()
