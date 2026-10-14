const { chromium } = require('C:/Users/wing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
(async () => {
  const browser = await chromium.launch({headless:true,executablePath:'C:/Users/wing/AppData/Local/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-win64/chrome-headless-shell.exe'});
  try {
    const page = await browser.newPage();
    const errors=[];
    page.on('pageerror', e => errors.push(e.message));
    const results=[];
    for (const width of [375,768,1280]) {
      await page.setViewportSize({width,height:900});
      await page.goto(pathToFileURL(path.join(__dirname,'r01/antigen-report.html')).href);
      await page.locator('h1').waitFor();
      const read = () => page.evaluate(() => ({width:innerWidth,bodyWidth:document.documentElement.scrollWidth,
        tables:document.querySelectorAll('table').length, plots:document.querySelectorAll('svg').length,
        headings:[...document.querySelectorAll('h2')].map(h=>h.textContent)}));
      const closed=await read();
      await page.screenshot({path:path.join(__dirname,`r01/report-${width}.png`)});
      await page.evaluate(() => document.querySelectorAll('details').forEach(d=>d.open=true));
      const expanded=await read();
      if (expanded.bodyWidth>width || closed.bodyWidth>width) throw new Error('Page overflows at '+width);
      results.push({closed,expanded});
      if (width===1280) {
        await page.locator('#s4').screenshot({path:path.join(__dirname,'r01/report-permissions.png')});
        await page.locator('#s3').screenshot({path:path.join(__dirname,'r01/report-developability.png')});
      }
    }
    await page.emulateMedia({media:'print'});
    const print=await page.evaluate(() => ({bodyWidth:document.documentElement.scrollWidth,viewport:innerWidth}));
    if(errors.length) throw new Error(errors.join('\n'));
    fs.writeFileSync(path.join(__dirname,'layout-check.json'),JSON.stringify({status:'PASS',results,print,errors},null,2));
    console.log(JSON.stringify({status:'PASS',viewports:results.length,errors}));
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exit(1)});
