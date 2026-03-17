const { execSync } = require('child_process');
const path = require('path');

const frontendDir = path.join(
  'c:', 'Users', 'Pranesh', 'OneDrive', 'Music',
  'ARGUS Agentic Graph Forensics for Autonomous AML Investigation & SAR Generation',
  'argus-app', 'frontend'
);

try {
  execSync('npx vitest run --reporter=verbose', {
    cwd: frontendDir,
    encoding: 'utf-8',
    stdio: 'inherit',
  });
} catch (e) {
  process.exit(e.status || 1);
}
