import {pathToFileURL,fileURLToPath} from 'node:url';
import {dirname} from 'node:path';
const {chromium}=await import(process.env.NEBULA_PLAYWRIGHT ? pathToFileURL(process.env.NEBULA_PLAYWRIGHT).href : 'playwright');
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const out=dirname(fileURLToPath(import.meta.url));
const browser=await chromium.launch({channel:'msedge',headless:false,args:['--disable-backgrounding-occluded-windows','--disable-renderer-backgrounding']});
try{
 const context=await browser.newContext({viewport:{width:1600,height:900},deviceScaleFactor:1}); const page=await context.newPage(); const errors=[];
 page.on('pageerror',error=>errors.push(error.message)); page.on('console',m=>{if(['error','warning'].includes(m.type()))errors.push(m.text());});
 await page.goto('http://127.0.0.1:18126/?diagnostics=1',{waitUntil:'networkidle'});
 await page.getByRole('button',{name:'运行交互检查',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#diagnostics').dataset.finished==='true',null,{timeout:30000});
 const checks=JSON.parse(await page.locator('#diagnostics').getAttribute('data-checks')); assert.equal(checks.length,24); assert.ok(checks.every(c=>c.passed),JSON.stringify(checks));
 await fs.writeFile(out+'/interaction-checks.json',JSON.stringify(checks,null,2));
 await page.waitForFunction(()=>{try{return JSON.parse(document.querySelector('#stats').textContent).selected===null}catch{return false}});
 const read=async()=>JSON.parse(await page.locator('#stats').innerText()); const before=await read();
 await page.mouse.click(515,476); await page.waitForFunction(()=>document.querySelector('#node-label').textContent.includes('后端工程师')&&!document.querySelector('#node-label').hidden);
 await page.waitForFunction(()=>{try{return JSON.parse(document.querySelector('#stats').textContent).selected==='demo:0:0'}catch{return false}});
 const selected=await read(); assert.deepEqual(selected.camera,before.camera); assert.deepEqual(selected.target,before.target);
 await page.mouse.wheel(0,-120); await page.waitForFunction(distance=>JSON.parse(document.querySelector('#stats').textContent).distance<distance,selected.distance); const zoomed=await read(); assert.equal(zoomed.speed,selected.speed);
 await page.mouse.click(200,250); await page.waitForFunction(()=>document.querySelector('#node-label').hidden); await page.waitForFunction(()=>JSON.parse(document.querySelector('#stats').textContent).selected===null);
 const unselected=await read(); await page.mouse.wheel(0,-120); await page.waitForFunction(speed=>JSON.parse(document.querySelector('#stats').textContent).speed>speed,unselected.speed); const accelerated=await read(); assert.equal(accelerated.distance,unselected.distance);
 await page.keyboard.down('d'); await page.waitForTimeout(400); await page.keyboard.up('d'); await page.waitForFunction(target=>JSON.stringify(JSON.parse(document.querySelector('#stats').textContent).target)!==JSON.stringify(target),accelerated.target);
 const pan=await read(); await page.getByLabel('输入保护测试').fill(''); await page.getByLabel('输入保护测试').pressSequentially('wasdqe'); await page.waitForTimeout(1100); const typed=await read(); assert.deepEqual(typed.camera,pan.camera); assert.deepEqual(typed.target,pan.target);
 await fs.writeFile(out+'/native-inputs.json',JSON.stringify({before,selected,zoomed,unselected,accelerated,pan,typed,result:'native mouse selection/no recenter, wheel split, held D pan, actual input typing protected'},null,2));
 await fs.writeFile(out+'/interaction-console.json',JSON.stringify(errors,null,2)); assert.equal(errors.length,0);
 console.log(JSON.stringify({checks:checks.length,nativeInputs:'passed',errors})); await context.close();
}finally{await browser.close();}
