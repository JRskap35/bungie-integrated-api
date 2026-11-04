const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  for (const vp of [{width: 1440, height: 900}, {width: 390, height: 844}]) {
    const p = await (await b.newContext({viewport: vp})).newPage(); const log = [];
    p.on('pageerror', e => log.push('PAGE ERROR: ' + e.message));
    p.on('console', m => { if (['error', 'warning'].includes(m.type())) log.push('console ' + m.type() + ': ' + m.text().slice(0, 300)); });
    p.on('requestfailed', r => log.push('request failed: ' + r.url().slice(0, 120) + ' ' + (r.failure() || {}).errorText));
    const t0 = Date.now(); let status = null;
    try { const r = await p.goto('https://endgameapi.pages.dev/', {waitUntil: 'domcontentloaded', timeout: 60000}); status = r && r.status(); }
    catch (e) { log.push('NAVIGATION: ' + e.message.split('\n')[0]); }
    console.log(`viewport ${vp.width}: status ${status}, DOM ready after ${Date.now() - t0} ms`);
    await p.waitForTimeout(8000);
    const st = await p.evaluate(() => ({ready: document.readyState, rows: document.querySelectorAll('#list tr.row, #list .wcard').length,
      main: (document.querySelector('#main') || {}).innerHTML ? document.querySelector('#main').innerHTML.length : -1,
      sync: (document.querySelector('#sync .label') || {}).textContent, title: document.title, bytes: document.documentElement.outerHTML.length})).catch(e => ({err: e.message}));
    console.log(JSON.stringify(st));
    log.slice(0, 25).forEach(l => console.log('  ' + l));
    await p.screenshot({path: `live_${vp.width}.png`});
  }
  await b.close();
})();
