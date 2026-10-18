// Baseline is a Git replay of 7edfea6 with only matching DEV capture bookmarks.
import {pathToFileURL,fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
const {chromium}=await import(process.env.NEBULA_PLAYWRIGHT ? pathToFileURL(process.env.NEBULA_PLAYWRIGHT).href : 'playwright');
import fs from 'node:fs/promises';
const out=dirname(fileURLToPath(import.meta.url));
const mode=process.argv[2]??'capture';
const browser=await chromium.launch({channel:'msedge',headless:false,args:['--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding']});
try {
  const context=await browser.newContext({viewport:{width:mode==='perf'?1699:1600,height:mode==='perf'?901:900},deviceScaleFactor:mode==='perf'?1.5:1});
  const errors=[];
  const roots=[['before','/.p1a-baseline/index.html'],['after','/']];
  for(const [label,path] of roots){
    if(mode==='perf'){
      for(const view of ['overview','core','arm']){
        const page=await context.newPage(); page.on('pageerror',error=>errors.push({label,view,message:error.message})); page.on('console',message=>{if(['error','warning'].includes(message.type()))errors.push({label,view,type:message.type(),message:message.text()});});
        await page.goto(`http://127.0.0.1:18126${path}?diagnostics=1&view=${view==='arm'?'near':view}`,{waitUntil:'networkidle'});
        await page.waitForTimeout(3000); await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange'))); await page.waitForFunction(()=>{try{return JSON.parse(document.querySelector('#stats').textContent).frameSamples>=300}catch{return false}},null,{timeout:30000});
        const stats=JSON.parse(await page.locator('#stats').innerText());
        await fs.writeFile(`${out}/${label}-performance-${view}.json`,JSON.stringify(stats,null,2));
        console.log(JSON.stringify({label,view,...stats})); await page.close();
      }
    }else{
      for(const view of ['overview','core','arm','selected']){
        const page=await context.newPage(); page.on('pageerror',error=>errors.push({label,view,message:error.message})); page.on('console',message=>{if(['error','warning'].includes(message.type()))errors.push({label,view,type:message.type(),message:message.text()});});
        await page.goto(`http://127.0.0.1:18126${path}?still=1&view=${view==='arm'?'near':view}`,{waitUntil:'networkidle'});
        await page.waitForFunction(()=>document.querySelector('#universe')?.dataset.capture);
        await page.screenshot({path:`${out}/${label}-${view}.png`,scale:'css'});
        await fs.writeFile(`${out}/${label}-${view}.json`,await page.locator('#universe').getAttribute('data-capture'));
        await page.close();
      }
    }
  }
  await fs.writeFile(`${out}/${mode}-console.json`,JSON.stringify(errors,null,2));
  console.log(JSON.stringify({mode,browser:browser.version(),errors}));
  await context.close();
}finally{await browser.close();}
