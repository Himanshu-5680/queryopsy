package com.himanshu.queryopsy;

import android.app.Activity;
import android.content.Intent;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.util.Base64;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import android.window.OnBackInvokedCallback;
import android.window.OnBackInvokedDispatcher;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Queryopsy Android shell.
 *
 * The web app (HTML/CSS + Python on Pyodide/WebAssembly) ships inside the APK under assets/www and is
 * served from the virtual origin https://appassets.androidplatform.net/www/ - the same scheme AndroidX
 * WebViewAssetLoader uses - with correct MIME types (application/wasm lets WebAssembly stream-compile).
 * Every other URL is refused, file:// access is off and the app has no INTERNET permission.
 */
public class MainActivity extends Activity {
    private static final String HOST = "appassets.androidplatform.net";
    private static final String START = "https://" + HOST + "/www/index.html";
    private static final int SAVE_REQUEST = 41;

    private WebView web;
    private Object backCallback;
    private byte[] pendingBytes;

    private static final Map<String, String> MIME = new HashMap<>();
    static {
        MIME.put("html", "text/html"); MIME.put("js", "text/javascript"); MIME.put("css", "text/css");
        MIME.put("json", "application/json"); MIME.put("webmanifest", "application/manifest+json");
        MIME.put("wasm", "application/wasm"); MIME.put("zip", "application/zip"); MIME.put("whl", "application/zip");
        MIME.put("py", "text/plain"); MIME.put("sql", "text/plain"); MIME.put("txt", "text/plain");
        MIME.put("sqlite", "application/octet-stream"); MIME.put("woff2", "font/woff2");
        MIME.put("svg", "image/svg+xml"); MIME.put("png", "image/png");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        WebView.setWebContentsDebuggingEnabled(false);
        web = new WebView(this);
        web.setBackgroundColor(getResources().getColor(R.color.bg, getTheme()));
        setContentView(web);
        applyInsets();

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);                 // needed for the Pyodide bootstrap
        s.setDomStorageEnabled(true);                 // progress lives in localStorage on the device
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setGeolocationEnabled(false);
        s.setSupportMultipleWindows(false);
        s.setJavaScriptCanOpenWindowsAutomatically(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setBlockNetworkLoads(true);                 // belt and braces: nothing may leave the device
        s.setMediaPlaybackRequiresUserGesture(true);
        s.setSaveFormData(false);
        s.setTextZoom(100);
        if (Build.VERSION.SDK_INT >= 26) s.setSafeBrowsingEnabled(false);
        if (Build.VERSION.SDK_INT >= 33) s.setAlgorithmicDarkeningAllowed(false);
        else if (Build.VERSION.SDK_INT >= 29) s.setForceDark(WebSettings.FORCE_DARK_OFF);

        web.addJavascriptInterface(new AppBridge(), "AndroidApp");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
                return serve(req.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                if (HOST.equals(u.getHost()) && "https".equals(u.getScheme())) return false;
                return true;   // links to GitHub etc. are not opened (no network in this app)
            }
        });

        if (Build.VERSION.SDK_INT >= 33) {
            OnBackInvokedCallback cb = this::handleBack;
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, cb);
            backCallback = cb;
        }
        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(START);
    }

    private void applyInsets() {
        if (Build.VERSION.SDK_INT >= 30) {
            web.setOnApplyWindowInsetsListener((View v, WindowInsets in) -> {
                Insets i = in.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                Insets ime = in.getInsets(WindowInsets.Type.ime());
                v.setPadding(i.left, i.top, i.right, Math.max(i.bottom, ime.bottom));
                return WindowInsets.CONSUMED;
            });
        } else {
            web.setFitsSystemWindows(true);
        }
    }

    private WebResourceResponse serve(Uri u) {
        if (!"https".equals(u.getScheme()) || !HOST.equals(u.getHost())) return status(403, "Forbidden");
        String path = u.getPath();
        if (path == null || !path.startsWith("/www/") || path.contains("..")) return status(403, "Forbidden");
        String asset = path.substring(1);
        String ext = asset.substring(asset.lastIndexOf('.') + 1).toLowerCase(Locale.ROOT);
        String mime = MIME.get(ext);
        if (mime == null) return status(404, "Not Found");
        try {
            InputStream in = getAssets().open(asset, AssetManager.ACCESS_STREAMING);
            Map<String, String> h = new HashMap<>();
            h.put("X-Content-Type-Options", "nosniff");
            h.put("Access-Control-Allow-Origin", "https://" + HOST);
            h.put("Cache-Control", "no-cache");
            String enc = mime.startsWith("text/") || mime.endsWith("json") ? "utf-8" : null;
            return new WebResourceResponse(mime, enc, 200, "OK", h, in);
        } catch (IOException e) {
            return status(404, "Not Found");
        }
    }

    private static WebResourceResponse status(int code, String reason) {
        return new WebResourceResponse("text/plain", "utf-8", code, reason, new HashMap<>(), new ByteArrayInputStream(new byte[0]));
    }

    /** Back: close an open dialog, else leave a case for the case list, else exit. */
    private void handleBack() {
        if (web == null) { finish(); return; }
        String js = "(function(){var o=document.getElementById('overlay');if(o&&o.innerHTML){o.innerHTML='';return '1';}"
                + "if((location.hash||'').indexOf('#/case/')===0){location.hash='#/';return '1';}return '0';})()";
        web.evaluateJavascript(js, v -> { if (v == null || !v.contains("1")) { if (!moveTaskToBack(true)) finish(); } });
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() { handleBack(); }

    @Override
    protected void onSaveInstanceState(Bundle out) { super.onSaveInstanceState(out); if (web != null) web.saveState(out); }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != SAVE_REQUEST) return;
        byte[] bytes = pendingBytes;
        pendingBytes = null;
        if (resultCode != RESULT_OK || data == null || data.getData() == null || bytes == null) return;
        try (OutputStream out = getContentResolver().openOutputStream(data.getData())) {
            if (out == null) throw new IOException("no stream");
            out.write(bytes);
            Toast.makeText(this, "Certificate saved", Toast.LENGTH_SHORT).show();
        } catch (IOException e) {
            Toast.makeText(this, "Could not save the file", Toast.LENGTH_LONG).show();
        }
    }

    @Override
    protected void onDestroy() {
        if (Build.VERSION.SDK_INT >= 33 && backCallback != null)
            getOnBackInvokedDispatcher().unregisterOnBackInvokedCallback((OnBackInvokedCallback) backCallback);
        if (web != null) { web.removeJavascriptInterface("AndroidApp"); web.destroy(); }
        super.onDestroy();
    }

    /** Small, explicit surface exposed to the page. */
    private final class AppBridge {
        /** Save a generated certificate through the system "Save as" picker (no storage permission needed). */
        @JavascriptInterface
        public void saveFile(String name, String mime, String base64) {
            final byte[] bytes;
            try { bytes = Base64.decode(base64, Base64.DEFAULT); } catch (IllegalArgumentException e) { return; }
            if (bytes.length > 20 * 1024 * 1024) return;
            final String safeName = name == null ? "certificate" : name.replaceAll("[^A-Za-z0-9._-]", "_");
            final String safeMime = "application/pdf".equals(mime) ? mime : "image/png";
            runOnUiThread(() -> {
                pendingBytes = bytes;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType(safeMime);
                i.putExtra(Intent.EXTRA_TITLE, safeName);
                try { startActivityForResult(i, SAVE_REQUEST); }
                catch (Exception e) { pendingBytes = null; Toast.makeText(MainActivity.this, "No file picker available", Toast.LENGTH_LONG).show(); }
            });
        }

        /** Match status/navigation bar colours to the in-app theme. */
        @JavascriptInterface
        public void setDark(boolean dark) {
            runOnUiThread(() -> {
                Window w = getWindow();
                int c = dark ? Color.parseColor("#121212") : Color.parseColor("#F4F0EA");
                w.setStatusBarColor(c);
                w.setNavigationBarColor(c);
                web.setBackgroundColor(c);
                if (Build.VERSION.SDK_INT >= 23) {
                    int flags = w.getDecorView().getSystemUiVisibility();
                    flags = dark ? (flags & ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR) : (flags | View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
                    w.getDecorView().setSystemUiVisibility(flags);
                }
            });
        }
    }
}
