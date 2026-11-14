// Queryopsy bootstrap - the only JavaScript in the app.
// Starts the bundled Pyodide runtime (no CDN), loads its sqlite3 module and hands control to Python (src/main.py).
(async () => {
  const say = (t) => {
    const el = document.getElementById('engine-status'); if (el) el.innerHTML = '<span>' + t + '</span>';
    const sp = document.getElementById('splash-status'); if (sp) sp.textContent = t;
  };
  const PY = ['main.py', 'engine/__init__.py', 'engine/validator.py', 'engine/runner.py', 'engine/errors.py', 'engine/sqltools.py',
    'ui/__init__.py', 'ui/app.py', 'ui/appmode.py', 'ui/dom.py', 'ui/editor.py', 'ui/store.py', 'ui/theme_toggle.py'];
  try {
    if ('serviceWorker' in navigator && location.protocol === 'https:' && !location.hostname.startsWith('appassets')) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }
    say('Starting Python...');
    const py = await loadPyodide({ indexURL: new URL('vendor/pyodide/', location.href).href });
    say('Loading SQLite...');
    await py.loadPackage('sqlite3', { messageCallback: () => {} });
    const files = PY.map((f) => ['src/' + f, '/app/' + f]).concat([['reports/__init__.py', '/app/reports/__init__.py'],
      ['reports/audit_certificate.py', '/app/reports/audit_certificate.py']]);
    await Promise.all(files.map(async ([url, dest]) => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(url + ' ' + res.status);
      py.FS.mkdirTree(dest.slice(0, dest.lastIndexOf('/')));
      py.FS.writeFile(dest, await res.text());
    }));
    py.runPython("import sys; sys.path.insert(0, '/app')");
    window.queryopsy = await py.runPythonAsync('import main\nawait main.start()');
  } catch (err) {
    console.error(err);
    say('Engine failed to start');
    const sp = document.getElementById('splash'); if (sp) sp.classList.add('failed');
    const box = document.getElementById('boot-error');
    if (box) { box.hidden = false; box.querySelector('code').textContent = String(err && err.message || err); }
  }
})();
