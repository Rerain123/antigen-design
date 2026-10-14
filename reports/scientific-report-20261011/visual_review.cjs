const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require(process.env.T01_PLAYWRIGHT_MODULE);
(async()=>{
 const out=__dirname;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100},offline:true});
  await page.goto(pathToFileURL(path.join(out,'20261011-073807-7ff412a6-scientific-report.html')).href);
  await page.screenshot({path:path.join(out,'desktop-cover.png')});
  await page.locator('#candidate-1>summary').click();
  await page.locator('#candidate-1').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'candidate-details.png')});
  await page.locator('#candidate-1>summary').click();
  await page.emulateMedia({media:'print'});
  const printed=await page.locator('#candidate-1 .candidate-body').evaluate(e=>({height:e.getBoundingClientRect().height,display:getComputedStyle(e).display}));
  if(!printed.height)throw Error('Candidate scientific results hidden from print');
  await page.locator('#candidate-1').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'print-candidate.png')});
  await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:path.join(out,'mobile-cover.png')});
  await page.locator('#s4').scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(out,'mobile-results.png')});
  fs.writeFileSync(path.join(out,'print-check.json'),JSON.stringify({status:'PASS',printed},null,2));
  console.log(JSON.stringify({status:'PASS',printed}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
