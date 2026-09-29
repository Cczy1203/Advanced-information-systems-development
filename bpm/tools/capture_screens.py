#!/usr/bin/env python3
"""Capture Operate and Tasklist screenshots from the running c8run webapps.

The c8run webapps sit behind a form login at /operate and /tasklist.  A headless
Chrome driven by puppeteer is the only thing that gets past it here: the JSON
session endpoint answers 401 even with basic auth, so plain curl cannot be used.

Usage:  python3 capture_screens.py [out-dir]
"""
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "screenshots"))
BASE = "http://localhost:8080"

JS = textwrap.dedent(
    """
    const puppeteer = require('puppeteer-core');
    const OUT = process.env.SHOT_DIR;

    const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

    async function login(page, app) {
      await page.goto(`${process.env.BASE}/${app}/`, { waitUntil: 'networkidle2', timeout: 60000 });
      const has = async (sel) => (await page.$(sel)) !== null;
      if (await has('input[name="username"]')) {
        await page.type('input[name="username"]', 'demo', { delay: 20 });
        await page.type('input[name="password"]', 'demo', { delay: 20 });
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 60000 }).catch(() => {}),
          page.click('button[type="submit"]'),
        ]);
      }
      await new Promise(r => setTimeout(r, 4000));
      return page.url();
    }

    (async () => {
      const browser = await puppeteer.launch({
        executablePath: CHROME,
        headless: 'new',
        args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1920,1200'],
        defaultViewport: { width: 1920, height: 1200 },
      });
      const page = await browser.newPage();
      page.on('console', () => {});

      for (const [app, file, extra] of [
        ['operate', 'operate-dashboard.png', null],
        ['tasklist', 'tasklist-open-tasks.png', null],
      ]) {
        const url = await login(page, app);
        console.log(`${app} landed on ${url}`);
        if (extra) { await page.goto(extra, { waitUntil: 'networkidle2' }); await new Promise(r => setTimeout(r, 4000)); }
        await page.screenshot({ path: `${OUT}/${file}` });
        console.log(`wrote ${file}`);
      }
      await browser.close();
    })().catch(e => { console.error('FAILED', e.message); process.exit(1); });
    """
)

def main():
    runner = "/tmp/lint"
    script = os.path.join(runner, "_capture.js")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(JS)
    env = dict(os.environ, SHOT_DIR=OUT, BASE=BASE)
    proc = subprocess.run(["node", script], cwd=runner, env=env,
                          capture_output=True, text=True, timeout=420)
    print(proc.stdout.strip())
    if proc.returncode != 0:
        print(proc.stderr.strip()[-2000:])
        return proc.returncode
    return 0

if __name__ == "__main__":
    sys.exit(main())
