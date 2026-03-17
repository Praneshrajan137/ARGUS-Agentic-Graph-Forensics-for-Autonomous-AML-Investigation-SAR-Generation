const { execSync } = require('child_process');
const path = require('path');

// Resolve the frontend directory relative to this script's location
const cwd = path.resolve(__dirname);
try {
  execSync('npx vitest run --reporter=verbose', {
    cwd,
    encoding: 'utf8',
    stdio: 'inherit',
    env: { ...process.env, FORCE_COLOR: '0' },
  });
} catch (e) {
  process.exit(e.status || 1);
}
