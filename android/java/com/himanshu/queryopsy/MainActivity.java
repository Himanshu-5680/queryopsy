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
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.Window;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
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
    /** Last system-bar insets in CSS px, re-sent to the page after every load. */
    private String insetJs = "";
    private boolean darkUi;

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
        darkUi = (getResources().getConfiguration().uiMode & android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                == android.content.res.Configuration.UI_MODE_NIGHT_YES;
        web = new WebView(this);
        web.setBackgroundColor(getResources().getColor(R.color.bg, getTheme()));
        web.setOverScrollMode(View.OVER_SCROLL_NEVER);
        web.setHapticFeedbackEnabled(true);
        setContentView(web);
        setupWindow();
        applyBarAppearance(darkUi);
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
            public void onPageFinished(WebView view, String url) {
                if (!insetJs.isEmpty()) view.evaluateJavascript(insetJs, null);
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

    /**
     * Edge-to-edge on Android 11+: the page draws under transparent status and navigation bars and gets the
     * bar sizes as CSS variables (--a-top/--a-bottom/--a-left/--a-right), like iOS safe-area insets.
     * Older versions keep solid bars that match the app background.
     */
    private void setupWindow() {
        Window w = getWindow();
        if (Build.VERSION.SDK_INT >= 28) {
            WindowManager.LayoutParams lp = w.getAttributes();
            lp.layoutInDisplayCutoutMode = WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
            w.setAttributes(lp);
        }
        if (Build.VERSION.SDK_INT >= 30) {
            w.setDecorFitsSystemWindows(false);
            w.setStatusBarColor(Color.TRANSPARENT);
            w.setNavigationBarColor(Color.TRANSPARENT);
            w.setStatusBarContrastEnforced(false);
            w.setNavigationBarContrastEnforced(false);
        }
    }

    private void applyInsets() {
        if (Build.VERSION.SDK_INT >= 30) {
            web.setOnApplyWindowInsetsListener((View v, WindowInsets in) -> {
                Insets bars = in.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                Insets ime = in.getInsets(WindowInsets.Type.ime());
                boolean imeOn = in.isVisible(WindowInsets.Type.ime()) && ime.bottom > bars.bottom;
                // only the keyboard shrinks the WebView; the bars are handled in CSS so content can scroll under them
                v.setPadding(0, 0, 0, imeOn ? ime.bottom : 0);
                float d = getResources().getDisplayMetrics().density;
                insetJs = String.format(Locale.ROOT,
                        "(function(){var s=document.documentElement.style;s.setProperty('--a-top','%.1fpx');"
                                + "s.setProperty('--a-bottom','%.1fpx');s.setProperty('--a-left','%.1fpx');s.setProperty('--a-right','%.1fpx');"
                                + "document.documentElement.classList.toggle('ime',%b);})()",
                        bars.top / d, imeOn ? 0f : bars.bottom / d, bars.left / d, bars.right / d, imeOn);
                v.post(() -> web.evaluateJavascript(insetJs, null));
                return WindowInsets.CONSUMED;
            });
        } else {
            web.setFitsSystemWindows(true);
        }
    }

    /** Status/navigation bar icons: dark icons on the light theme, light icons on the dark theme. */
    @SuppressWarnings("deprecation")
    private void applyBarAppearance(boolean dark) {
        Window w = getWindow();
        int bg = dark ? Color.parseColor("#0B0A09") : Color.parseColor("#F2F1EE");
        web.setBackgroundColor(bg);
        w.getDecorView().setBackgroundColor(bg);
        if (Build.VERSION.SDK_INT >= 30) {
            WindowInsetsController c = w.getInsetsController();
            if (c != null) {
                int mask = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                c.setSystemBarsAppearance(dark ? 0 : mask, mask);
            }
        } else {
            w.setStatusBarColor(Build.VERSION.SDK_INT >= 23 ? bg : Color.BLACK);
            w.setNavigationBarColor(Build.VERSION.SDK_INT >= 26 ? bg : Color.BLACK);
            int flags = w.getDecorView().getSystemUiVisibility();
            if (Build.VERSION.SDK_INT >= 23) {
                if (dark) flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR; else flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            }
            if (Build.VERSION.SDK_INT >= 26) {
                if (dark) flags &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR; else flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
            }
            w.getDecorView().setSystemUiVisibility(flags);
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

    /** Back pops the in-app navigation stack (sheets, dialogs, keyboard, then screens - handled in Python); on the home screen the app goes to the background. */
    private void handleBack() {
        if (web == null) { finish(); return; }
        String js = "(function(){try{if(window.queryopsyBack){return String(window.queryopsyBack());}}catch(e){}"
                + "var o=document.getElementById('overlay');if(o&&o.innerHTML){o.innerHTML='';return '1';}"
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

        /** Match the system bars to the in-app theme (called by the page whenever the theme changes). */
        @JavascriptInterface
        public void setDark(boolean dark) {
            runOnUiThread(() -> { darkUi = dark; applyBarAppearance(dark); });
        }

        /** Native haptic tick for taps and verdicts; uses the view's haptic feedback, so no VIBRATE permission is needed. */
        @JavascriptInterface
        public void haptic(String kind) {
            runOnUiThread(() -> {
                int c;
                if ("success".equals(kind)) c = Build.VERSION.SDK_INT >= 30 ? HapticFeedbackConstants.CONFIRM : HapticFeedbackConstants.VIRTUAL_KEY;
                else if ("error".equals(kind)) c = Build.VERSION.SDK_INT >= 30 ? HapticFeedbackConstants.REJECT : HapticFeedbackConstants.LONG_PRESS;
                else c = Build.VERSION.SDK_INT >= 27 ? HapticFeedbackConstants.KEYBOARD_TAP : HapticFeedbackConstants.VIRTUAL_KEY;
                web.performHapticFeedback(c);
            });
        }
    }
}
