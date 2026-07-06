/* Smoke test do dashboard estático.
   - Sobe um servidor HTTP local para web/
   - Abre as principais rotas/deep links
   - Garante que não há console.error/pageerror
*/
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const PORT = Number(process.env.PORT || 8787);
const ROOT = process.cwd();
const PY = process.env.PYTHON || 'python3';
const BASE = `http://127.0.0.1:${PORT}/index.html`;

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }

async function waitForServer(timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(BASE);
      if (res.ok) return;
    } catch (_) {}
    await wait(250);
  }
  throw new Error(`Servidor local não respondeu em ${BASE}`);
}

async function main() {
  const server = spawn(PY, ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', 'web'], {
    cwd: ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let serverLog = '';
  server.stdout.on('data', d => { serverLog += d.toString(); });
  server.stderr.on('data', d => { serverLog += d.toString(); });

  try {
    await waitForServer();
    const browser = await chromium.launch({ args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } });

    // Reproduz o bug que já apareceu em produção: a campeã determinística
    // (bracket) fica em 2º no ranking de probabilidade e era renderizada duas
    // vezes no pódio do overview. Só mockamos o primeiro carregamento.
    const wcDataSrc = fs.readFileSync(path.join(ROOT, 'web', 'wc_data.js'), 'utf8');
    let mockOverviewData = true;
    await page.route('**/wc_data.js*', async route => {
      if (!mockOverviewData) return route.continue();
      mockOverviewData = false;
      const raw = wcDataSrc.slice(wcDataSrc.indexOf('window.WC_DATA = ') + 'window.WC_DATA = '.length).trim().replace(/;$/, '');
      const data = JSON.parse(raw);
      // Espanha vira #1 e Argentina (#36, campeã no bracket) cai para #2.
      data.titleProb['28'] = 25;
      data.titleProb['36'] = 18;
      await route.fulfill({
        contentType: 'application/javascript',
        body: `/* smoke mock */\nwindow.WC_DATA = ${JSON.stringify(data)};`,
      });
    });

    const errors = [];
    page.on('console', msg => { if (msg.type() === 'error') errors.push(msg.text()); });
    page.on('pageerror', err => errors.push(`PAGEERR: ${err.message}`));

    async function goto(hash) {
      await page.goto(BASE + hash, { waitUntil: 'networkidle' });
      await page.waitForSelector('.nav button', { timeout: 15000 });
      await page.waitForTimeout(350);
    }

    await goto('#/overview');
    await page.waitForSelector('.model-perf');
    const heroChamp = (await page.locator('.cb-champ .n').innerText()).trim();
    const heroRunners = await page.locator('.cb-runner .nm').evaluateAll(els => els.map(e => e.textContent.trim()));
    if (heroRunners.includes(heroChamp)) throw new Error(`Overview duplicou a campeã no pódio: ${heroChamp}`);

    await goto('#/calendario?team=brasil&group=C');
    await page.waitForSelector('.cal-advanced');
    const calText = await page.locator('body').innerText();
    if (!/Brasil/i.test(calText)) throw new Error('Filtro/deep link do calendário não exibiu Brasil.');

    await goto('#/selecao/brasil');
    await page.waitForSelector('.journey-head');
    if (!/Brasil/i.test(await page.locator('.journey-head').innerText())) throw new Error('Deep link de seleção não abriu Brasil.');

    await goto('#/comparador/brasil/argentina');
    await page.waitForSelector('.cmp-head');
    const cmp = await page.locator('.cmp-head').innerText();
    if (!/Brasil/i.test(cmp) || !/Argentina/i.test(cmp)) throw new Error('Deep link do comparador não abriu Brasil x Argentina.');

    await goto('#/calendario');
    await page.locator('.mtile').first().click();
    await page.waitForSelector('.modal-shell');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);

    const matchSlug = await page.evaluate(() => D.matchSlug(D.calendar[0]));
    await goto(`#/jogo/${matchSlug}`);
    await page.waitForSelector('.modal-shell');

    if (errors.length) throw new Error(`Erros de console:\n${errors.join('\n')}`);
    await browser.close();
  } finally {
    // Encerra apenas o servidor filho iniciado por este script.
    server.kill('SIGTERM');
    await wait(250);
    if (!server.killed && server.exitCode == null) server.kill('SIGTERM');
  }
}

main().catch(err => {
  console.error(err.stack || err.message);
  process.exit(1);
});
