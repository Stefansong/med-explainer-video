// 任意页面截图：node tools/shot.js <html?query> <out.png> [w=1080] [h=1920]   （styleframes / cover / test_chars 等自检页；页面要把 document.title 置为 'ready'）
const puppeteer = require('puppeteer-core'); const path = require('path');
const C = require('./_common.js');
(async () => {
  const [src, out, w = 1080, h = 1920] = process.argv.slice(2); const [file, q] = src.split('?');
  const b = await puppeteer.launch({ executablePath: C.CHROME, args: ['--allow-file-access-from-files'] });
  const p = await b.newPage(); await p.setViewport({ width: +w, height: +h });
  p.on('pageerror', (e) => console.log('PAGEERR', e.message)); p.on('console', (m) => m.type() === 'error' && console.log('CONSOLE', m.text()));
  await p.goto(C.fileUrl(file) + (q ? '?' + q : '')); await p.waitForFunction('document.title==="ready"', { timeout: 60000 });
  const el = await p.$('canvas'); await el.screenshot({ path: out }); await b.close(); console.log('→', out);
})();
