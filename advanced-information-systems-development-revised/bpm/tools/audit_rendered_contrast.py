#!/usr/bin/env python3
"""Measure WCAG contrast on a form as Tasklist actually renders it.

`docs/20` used to say contrast was not measured, and refused to claim WCAG
compliance on the strength of a static reading of the form JSON. It was right to
refuse: the form JSON says nothing about colour. This measures the real thing.

It drives the real Tasklist in headless Chrome, opens one task, and walks the text
nodes of the rendered form, working out each one's effective background by climbing
to the first ancestor that paints one, then applying the WCAG 2.1 relative-luminance
formula. Normal text needs 4.5:1, large text 3:1.

A control that is `disabled` (or `aria-disabled`) is recorded but marked exempt:
WCAG 1.4.3 excludes inactive user interface components, and the "Complete Task"
button is disabled until the required fields are filled - which is exactly the state
a freshly opened task is in, so counting it as a failure would be wrong.

Chrome driven by puppeteer is what gets past the Tasklist login, the same way
`tools/capture_screens.py` does it.

    python3 tools/audit_rendered_contrast.py <userTaskKey> [output.json]

Requires the runner set up once:

    mkdir -p /tmp/lint && cd /tmp/lint && npm install puppeteer-core
"""
import json
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "..", "screenshots", "v16", "tasklist-contrast.json")
BASE = "http://localhost:8080"

JS = textwrap.dedent(
    r"""
    const puppeteer = require('puppeteer-core');
    const fs = require('fs');
    const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
    const BASE = process.env.BASE;
    const TASK = process.env.TASK_KEY;
    const OUT = process.env.OUT_JSON;

    const MEASURE = () => {
      const parse = (value) => {
        const m = String(value).match(/rgba?\(([^)]+)\)/);
        if (!m) return null;
        const parts = m[1].split(',').map((p) => parseFloat(p.trim()));
        return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
      };
      const channel = (c) => {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      };
      const luminance = ([r, g, b]) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      const ratio = (a, b) => {
        const sorted = [luminance(a), luminance(b)].sort((x, y) => y - x);
        return (sorted[0] + 0.05) / (sorted[1] + 0.05);
      };
      const effectiveBackground = (el) => {
        let node = el;
        while (node && node !== document.documentElement) {
          const bg = parse(getComputedStyle(node).backgroundColor);
          if (bg && bg[3] > 0.5) return bg;
          node = node.parentElement;
        }
        return [255, 255, 255, 1];
      };
      const visible = (el) => {
        const style = getComputedStyle(el);
        if (style.visibility === 'hidden' || style.display === 'none') return false;
        if (parseFloat(style.opacity) < 0.1) return false;
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      };

      const findings = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        const text = (node.textContent || '').trim();
        if (!text) continue;
        const el = node.parentElement;
        if (!el || !visible(el)) continue;

        const style = getComputedStyle(el);
        const fg = parse(style.color);
        if (!fg) continue;
        const bg = effectiveBackground(el);
        const size = parseFloat(style.fontSize);
        const weight = parseInt(style.fontWeight, 10) || 400;
        const large = size >= 24 || (size >= 18.66 && weight >= 700);
        const required = large ? 3.0 : 4.5;
        const value = Math.round(ratio(fg, bg) * 100) / 100;

        findings.push({
          text: text.slice(0, 60),
          element: el.tagName.toLowerCase(),
          fontSize: size,
          bold: weight >= 700,
          large,
          required,
          ratio: value,
          passes: value >= required,
          color: style.color,
          background: 'rgb(' + bg[0] + ', ' + bg[1] + ', ' + bg[2] + ')',
          disabled: !!(el.closest('button')?.disabled || el.disabled
                       || el.getAttribute('aria-disabled') === 'true'),
        });
      }
      return findings;
    };

    (async () => {
      const browser = await puppeteer.launch({
        executablePath: CHROME,
        headless: 'new',
        args: ['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1600,1200'],
      });
      const page = await browser.newPage();
      await page.setViewport({ width: 1600, height: 1200 });

      await page.goto(`${BASE}/tasklist/`, { waitUntil: 'networkidle2', timeout: 90000 });
      if (await page.$('input[name="username"]')) {
        await page.type('input[name="username"]', 'demo', { delay: 20 });
        await page.type('input[name="password"]', 'demo', { delay: 20 });
        await Promise.all([
          page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 90000 }).catch(() => {}),
          page.click('button[type="submit"]'),
        ]);
      }
      await new Promise((r) => setTimeout(r, 6000));

      await page.goto(`${BASE}/tasklist/${TASK}`, { waitUntil: 'networkidle2', timeout: 90000 });
      await new Promise((r) => setTimeout(r, 7000));
      await page.waitForSelector('.fjs-form-field', { timeout: 60000 }).catch(() => {});

      const fields = await page.$$eval('.fjs-form-field', (els) => els.length);
      const findings = await page.evaluate(MEASURE);
      const failing = findings.filter((f) => !f.passes);
      const live = findings.filter((f) => !f.disabled);

      const summary = {
        method: 'headless Chrome against the running Tasklist, WCAG 2.1 relative luminance',
        task: TASK,
        url: page.url(),
        renderedFormFields: fields,
        textNodesMeasured: findings.length,
        failing: failing.length,
        failingExcludingDisabledControls: failing.filter((f) => !f.disabled).length,
        minimumRatioLiveText: live.length ? Math.min(...live.map((f) => f.ratio)) : null,
        maximumRatioLiveText: live.length ? Math.max(...live.map((f) => f.ratio)) : null,
        findings,
      };
      fs.writeFileSync(OUT, JSON.stringify(summary, null, 2));

      console.log('form fields rendered :', fields);
      console.log('text nodes measured  :', findings.length);
      console.log('below the WCAG floor :', failing.length,
                  '(disabled controls, exempt under 1.4.3:', failing.length - summary.failingExcludingDisabledControls, ')');
      console.log('lowest live ratio    :', summary.minimumRatioLiveText);
      await browser.close();
    })().catch((e) => { console.error('FAILED', e.message); process.exit(1); });
    """
)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    task_key = sys.argv[1]
    out = os.path.abspath(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT)

    runner = "/tmp/lint"
    os.makedirs(runner, exist_ok=True)
    script = os.path.join(runner, "_contrast.js")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(JS)

    env = dict(os.environ, BASE=BASE, TASK_KEY=str(task_key), OUT_JSON=out)
    try:
        proc = subprocess.run(["node", script], cwd=runner, env=env,
                              capture_output=True, text=True, timeout=420)
    except FileNotFoundError:
        print("node is not on PATH; the measurement needs node and puppeteer-core")
        return 1
    print(proc.stdout.strip())
    if proc.returncode != 0:
        print(proc.stderr.strip()[-2000:])
        return proc.returncode
    try:
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        return 1
    if data.get("failingExcludingDisabledControls"):
        print("FAIL: %d live text node(s) below the WCAG floor"
              % data["failingExcludingDisabledControls"])
        return 1
    print("OK: no live text below the WCAG floor; written to %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
