// Visual QA for the offline report; no remote browser or website access.
const fs = require('fs');
const path = require('path');
const {pathToFileURL} = require('url');
const {chromium} = require(process.env.T01_PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const file = path.resolve(process.argv[2]);
  const folder = path.dirname(file);
  const stem=path.basename(file,'.html');
  const executablePath = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Google/Chrome/Application/chrome.exe'
  ].find(fs.existsSync);
  const browser = await chromium.launch({headless:true, ...(executablePath ? {executablePath} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1050},offline:true});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(file).href);
    await page.screenshot({path:path.join(folder,stem+'-desktop.png'),fullPage:true});
    const desktop=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,title:document.title}));
    await page.locator('summary').first().click();
    if (!await page.locator('details').first().getAttribute('open').then(v=>v!==null)) throw Error('Disclosure did not open');
    const sizes=[];
    for (const width of [320,375,390,430,768,1024,1440]) {
      await page.setViewportSize({width,height:900});
      const size=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
        tableDisplay:getComputedStyle(document.querySelector('table')).display}));
      if(size.scrollWidth>width)throw Error('Horizontal page overflow at '+width);
      if(width<=680 && size.tableDisplay!=='block')throw Error('Mobile cards missing');
      sizes.push(size);
    }
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(folder,stem+'-mobile.png'),fullPage:true});
    await page.screenshot({path:path.join(folder,stem+'-mobile-top.png')});
    await page.locator('#s4').screenshot({path:path.join(folder,stem+'-mobile-candidates.png')});
    await page.locator('details').evaluateAll(nodes=>nodes.forEach(n=>n.open=true));
    const expanded=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);
    if(!expanded || errors.length)throw Error('Expanded layout or runtime error');
    const chart=page.locator('.chart-scroll').first();
    if(await chart.count()){
      await chart.evaluate(e=>{e.scrollLeft=200});
      if(await chart.evaluate(e=>e.scrollLeft)<=0)throw Error('Mobile chart does not scroll');
    }
    await page.emulateMedia({media:'print'});
    const print=await page.locator('nav').evaluate(e=>getComputedStyle(e).display);
    if(print!=='none')throw Error('Print style missing');
    const result={status:'PASS',desktop,sizes,expanded,printStyles:true,disclosure:true,errors};
    fs.writeFileSync(path.join(folder,stem+'-visual-check.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
