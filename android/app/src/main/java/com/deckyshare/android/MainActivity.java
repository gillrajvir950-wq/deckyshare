package com.deckyshare.android;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.Intent;
import android.content.SharedPreferences;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.content.pm.PackageManager;
import android.provider.OpenableColumns;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String PREFS = "deckyshare";
    private static final String ENDPOINT = "share_endpoint";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private EditText address;
    private EditText code;
    private TextView status;
    private ProgressBar progress;
    private Intent pendingShare;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        buildUi();
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            pendingShare = getIntent();
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 7);
        } else {
            acceptIntent(getIntent());
        }
    }

    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        acceptIntent(intent);
    }

    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(requestCode, permissions, results);
        if (requestCode == 7 && pendingShare != null) acceptIntent(pendingShare);
    }

    private void buildUi() {
        int pad = dp(20);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(pad, pad, pad, pad);
        root.setBackgroundColor(Color.rgb(13, 23, 38));

        TextView title = text("DeckyShare", 25, true);
        root.addView(title);
        TextView help = text("Pair once, then send from Android's Share menu.", 14, false);
        help.setTextColor(Color.rgb(190, 215, 235));
        root.addView(help, margins(0, dp(6), 0, dp(18)));

        address = input("Deck address, e.g. 192.168.1.42:8787");
        root.addView(address, margins(0, 0, 0, dp(10)));
        code = input("6-digit pairing code");
        code.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);
        root.addView(code, margins(0, 0, 0, dp(10)));

        Button pair = button("Pair with Steam Deck");
        pair.setOnClickListener(v -> pair());
        root.addView(pair, margins(0, 0, 0, dp(14)));

        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(1000);
        progress.setVisibility(View.GONE);
        root.addView(progress, margins(0, 0, 0, dp(10)));
        status = text(isPaired() ? "Paired — share a file to DeckyShare." : "Not paired yet.", 14, true);
        root.addView(status);
        setContentView(root);
    }

    private void acceptIntent(Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        if (!Intent.ACTION_SEND.equals(action) && !Intent.ACTION_SEND_MULTIPLE.equals(action)) return;
        pendingShare = intent;
        if (!isPaired()) {
            showStatus("Pair this phone before sending the shared item.", true);
            return;
        }
        sendIntent(intent);
    }

    private void pair() {
        String host = address.getText().toString().trim();
        String pin = code.getText().toString().trim();
        if (host.startsWith("http://")) host = host.substring(7);
        if (host.startsWith("https://")) host = host.substring(8);
        while (host.endsWith("/")) host = host.substring(0, host.length() - 1);
        if (host.isEmpty() || !pin.matches("\\d{6}")) {
            showStatus("Enter the Deck address and six-digit code.", true);
            return;
        }
        final String pairUrl = "http://" + host + "/shortcut/pair?code=" + Uri.encode(pin);
        showStatus("Pairing…", false);
        worker.execute(() -> {
            try {
                HttpURLConnection connection = open(pairUrl, "POST");
                connection.setFixedLengthStreamingMode(0);
                connection.connect();
                String body = readResponse(connection);
                if (connection.getResponseCode() != 200) throw new Exception(errorMessage(body, "Pairing failed"));
                String endpoint = new JSONObject(body).getString("endpoint");
                getSharedPreferences(PREFS, MODE_PRIVATE).edit().putString(ENDPOINT, endpoint).apply();
                runOnUiThread(() -> {
                    showStatus("Paired successfully.", false);
                    code.setText("");
                    if (pendingShare != null) sendIntent(pendingShare);
                });
            } catch (Exception error) {
                runOnUiThread(() -> showStatus(error.getMessage(), true));
            }
        });
    }

    private void sendIntent(Intent intent) {
        pendingShare = null;
        ShareUploadService.enqueue(this, intent);
        Toast.makeText(this, "Sending to Steam Deck in background", Toast.LENGTH_SHORT).show();
        finishAndRemoveTask();
    }

    private List<SharedItem> sharedItems(Intent intent) {
        List<SharedItem> out = new ArrayList<>();
        String action = intent.getAction();
        if (Intent.ACTION_SEND_MULTIPLE.equals(action)) {
            ArrayList<Uri> uris = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (uris != null) for (Uri uri : uris) addUri(out, uri, intent.getType());
        } else {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) addUri(out, uri, intent.getType());
            String text = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (uri == null && text != null) {
                byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
                out.add(new SharedItem("Shared Text.txt", "text/plain", bytes.length, () -> new ByteArrayInputStream(bytes)));
            }
        }
        return out;
    }

    private void addUri(List<SharedItem> out, Uri uri, String fallbackType) {
        ContentResolver resolver = getContentResolver();
        String name = "Shared File";
        long size = -1;
        try (Cursor cursor = resolver.query(uri, new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) name = cursor.getString(nameIndex);
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex);
            }
        } catch (Exception ignored) { }
        String type = resolver.getType(uri);
        if (type == null) type = fallbackType == null ? "application/octet-stream" : fallbackType;
        final long knownSize = size;
        final String finalName = name;
        final String finalType = type;
        out.add(new SharedItem(finalName, finalType, knownSize, () -> resolver.openInputStream(uri)));
    }

    private void upload(SharedItem item, int index, int count) throws Exception {
        if (item.size < 0) throw new Exception(item.name + ": Android provider did not report the file size");
        String endpoint = getSharedPreferences(PREFS, MODE_PRIVATE).getString(ENDPOINT, "");
        Uri original = Uri.parse(endpoint);
        Uri target = original.buildUpon().clearQuery()
                .appendQueryParameter("key", original.getQueryParameter("key"))
                .appendQueryParameter("name", item.name).build();
        HttpURLConnection connection = open(target.toString(), "POST");
        connection.setRequestProperty("Content-Type", item.contentType);
        connection.setFixedLengthStreamingMode(item.size);
        connection.setDoOutput(true);
        long sent = 0;
        byte[] buffer = new byte[1024 * 1024];
        try (InputStream in = item.source.open(); OutputStream output = connection.getOutputStream()) {
            if (in == null) throw new Exception("Cannot open " + item.name);
            int read;
            while ((read = in.read(buffer)) != -1) {
                output.write(buffer, 0, read);
                sent += read;
                final long done = sent;
                runOnUiThread(() -> {
                    int itemProgress = item.size == 0 ? 1000 : (int)Math.min(1000, done * 1000 / item.size);
                    progress.setProgress(((index * 1000) + itemProgress) / count);
                    status.setText("Sending " + (index + 1) + "/" + count + " • " + item.name);
                });
            }
        }
        String body = readResponse(connection);
        if (connection.getResponseCode() != 200) throw new Exception(errorMessage(body, "Upload failed"));
    }

    private HttpURLConnection open(String url, String method) throws Exception {
        HttpURLConnection connection = (HttpURLConnection)new URL(url).openConnection();
        connection.setRequestMethod(method);
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(120000);
        connection.setUseCaches(false);
        connection.setRequestProperty("User-Agent", "DeckyShare-Android/0.1");
        return connection;
    }

    private String readResponse(HttpURLConnection connection) throws Exception {
        InputStream input = connection.getResponseCode() >= 400 ? connection.getErrorStream() : connection.getInputStream();
        if (input == null) return "";
        try (InputStream in = input; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }

    private String errorMessage(String body, String fallback) {
        try { return new JSONObject(body).optString("error", fallback); }
        catch (Exception ignored) { return fallback; }
    }

    private boolean isPaired() {
        return !getSharedPreferences(PREFS, MODE_PRIVATE).getString(ENDPOINT, "").isEmpty();
    }

    private void showStatus(String message, boolean error) {
        status.setText(message == null ? "Unknown error" : message);
        status.setTextColor(error ? Color.rgb(255, 150, 150) : Color.rgb(170, 230, 255));
    }

    private TextView text(String value, int sp, boolean bold) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(Color.WHITE);
        if (bold) view.setTypeface(null, android.graphics.Typeface.BOLD);
        return view;
    }

    private EditText input(String hint) {
        EditText view = new EditText(this);
        view.setHint(hint);
        view.setSingleLine(true);
        view.setTextColor(Color.WHITE);
        view.setHintTextColor(Color.rgb(125, 155, 180));
        view.setBackgroundColor(Color.rgb(22, 42, 68));
        view.setPadding(dp(12), dp(10), dp(12), dp(10));
        return view;
    }

    private Button button(String label) {
        Button view = new Button(this);
        view.setText(label);
        view.setTextColor(Color.WHITE);
        view.setBackgroundColor(Color.rgb(45, 121, 183));
        return view;
    }

    private LinearLayout.LayoutParams margins(int left, int top, int right, int bottom) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.setMargins(left, top, right, bottom);
        return params;
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    @Override protected void onDestroy() {
        worker.shutdownNow();
        super.onDestroy();
    }

    private interface StreamSource { InputStream open() throws Exception; }
    private static final class SharedItem {
        final String name;
        final String contentType;
        final long size;
        final StreamSource source;
        SharedItem(String name, String contentType, long size, StreamSource source) {
            this.name = name;
            this.contentType = contentType;
            this.size = size;
            this.source = source;
        }
    }
}
