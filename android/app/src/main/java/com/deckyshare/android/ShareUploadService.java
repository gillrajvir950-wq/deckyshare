package com.deckyshare.android;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.ContentResolver;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.IBinder;
import android.provider.OpenableColumns;

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

public final class ShareUploadService extends Service {
    private static final String CHANNEL = "deckyshare_transfers";
    private static final int NOTIFICATION_ID = 9501;
    private static final String PREFS = "deckyshare";
    private static final String ENDPOINT = "share_endpoint";
    private final ExecutorService worker = Executors.newSingleThreadExecutor();

    public static void enqueue(Context context, Intent shareIntent) {
        Intent service = new Intent(context, ShareUploadService.class);
        service.setAction(shareIntent.getAction());
        service.setType(shareIntent.getType());
        service.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        if (shareIntent.getClipData() != null) service.setClipData(shareIntent.getClipData());
        if (Intent.ACTION_SEND_MULTIPLE.equals(shareIntent.getAction())) {
            service.putParcelableArrayListExtra(Intent.EXTRA_STREAM,
                    shareIntent.getParcelableArrayListExtra(Intent.EXTRA_STREAM));
        } else {
            Uri uri = shareIntent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) service.putExtra(Intent.EXTRA_STREAM, uri);
            String text = shareIntent.getStringExtra(Intent.EXTRA_TEXT);
            if (text != null) service.putExtra(Intent.EXTRA_TEXT, text);
        }
        context.startForegroundService(service);
    }

    @Override public void onCreate() {
        super.onCreate();
        NotificationManager manager = getSystemService(NotificationManager.class);
        NotificationChannel channel = new NotificationChannel(
                CHANNEL, "DeckyShare transfers", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("File transfer progress to Steam Deck");
        manager.createNotificationChannel(channel);
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        startForeground(NOTIFICATION_ID, notification("Preparing transfer…", 0, true));
        worker.execute(() -> runTransfer(intent, startId));
        return START_NOT_STICKY;
    }

    private void runTransfer(Intent intent, int startId) {
        try {
            List<SharedItem> items = sharedItems(intent);
            if (items.isEmpty()) throw new Exception("Shared item could not be read");
            for (int index = 0; index < items.size(); index++) upload(items.get(index), index, items.size());
            notifyFinal("Sent " + items.size() + (items.size() == 1 ? " item" : " items") + " to Steam Deck", false);
        } catch (Exception error) {
            notifyFinal(error.getMessage() == null ? "Transfer failed" : error.getMessage(), true);
        } finally {
            stopForeground(STOP_FOREGROUND_DETACH);
            stopSelf(startId);
        }
    }

    private List<SharedItem> sharedItems(Intent intent) {
        List<SharedItem> out = new ArrayList<>();
        if (intent == null) return out;
        if (Intent.ACTION_SEND_MULTIPLE.equals(intent.getAction())) {
            ArrayList<Uri> uris = intent.getParcelableArrayListExtra(Intent.EXTRA_STREAM);
            if (uris != null) for (Uri uri : uris) addUri(out, uri, intent.getType());
        } else {
            Uri uri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            if (uri != null) addUri(out, uri, intent.getType());
            String text = intent.getStringExtra(Intent.EXTRA_TEXT);
            if (uri == null && text != null) {
                byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
                out.add(new SharedItem("Shared Text.txt", "text/plain", bytes.length,
                        () -> new ByteArrayInputStream(bytes)));
            }
        }
        return out;
    }

    private void addUri(List<SharedItem> out, Uri uri, String fallbackType) {
        ContentResolver resolver = getContentResolver();
        String name = "Shared File";
        long size = -1;
        try (Cursor cursor = resolver.query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                int sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE);
                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) name = cursor.getString(nameIndex);
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) size = cursor.getLong(sizeIndex);
            }
        } catch (Exception ignored) { }
        String type = resolver.getType(uri);
        if (type == null) type = fallbackType == null ? "application/octet-stream" : fallbackType;
        final String finalName = name;
        final String finalType = type;
        final long finalSize = size;
        out.add(new SharedItem(finalName, finalType, finalSize, () -> resolver.openInputStream(uri)));
    }

    private void upload(SharedItem item, int index, int count) throws Exception {
        if (item.size < 0) throw new Exception(item.name + ": file size unavailable");
        String endpoint = getSharedPreferences(PREFS, MODE_PRIVATE).getString(ENDPOINT, "");
        if (endpoint.isEmpty()) throw new Exception("DeckyShare is not paired");
        Uri original = Uri.parse(endpoint);
        Uri target = original.buildUpon().clearQuery()
                .appendQueryParameter("key", original.getQueryParameter("key"))
                .appendQueryParameter("name", item.name).build();
        HttpURLConnection connection = (HttpURLConnection)new URL(target.toString()).openConnection();
        connection.setRequestMethod("POST");
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(120000);
        connection.setUseCaches(false);
        connection.setDoOutput(true);
        connection.setRequestProperty("User-Agent", "DeckyShare-Android/0.2");
        connection.setRequestProperty("Content-Type", item.contentType);
        connection.setFixedLengthStreamingMode(item.size);

        long sent = 0;
        long lastNotification = 0;
        byte[] buffer = new byte[1024 * 1024];
        try (InputStream input = item.source.open(); OutputStream output = connection.getOutputStream()) {
            if (input == null) throw new Exception("Cannot open " + item.name);
            int read;
            while ((read = input.read(buffer)) != -1) {
                output.write(buffer, 0, read);
                sent += read;
                long now = System.currentTimeMillis();
                if (now - lastNotification >= 500 || sent == item.size) {
                    lastNotification = now;
                    int fileProgress = item.size == 0 ? 1000 : (int)Math.min(1000, sent * 1000 / item.size);
                    int overall = ((index * 1000) + fileProgress) / count;
                    updateNotification("Sending " + (index + 1) + "/" + count + " • " + item.name, overall);
                }
            }
        }
        String body = readResponse(connection);
        if (connection.getResponseCode() != 200) throw new Exception(errorMessage(body, "Upload failed"));
    }

    private String readResponse(HttpURLConnection connection) throws Exception {
        InputStream input = connection.getResponseCode() >= 400
                ? connection.getErrorStream() : connection.getInputStream();
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

    private Notification notification(String message, int progress, boolean ongoing) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent pending = PendingIntent.getActivity(this, 0, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_upload)
                .setContentTitle("DeckyShare")
                .setContentText(message)
                .setContentIntent(pending)
                .setOnlyAlertOnce(true)
                .setOngoing(ongoing)
                .setColor(Color.rgb(102, 192, 244));
        if (ongoing) builder.setProgress(1000, progress, progress <= 0);
        return builder.build();
    }

    private void updateNotification(String message, int progress) {
        getSystemService(NotificationManager.class)
                .notify(NOTIFICATION_ID, notification(message, progress, true));
    }

    private void notifyFinal(String message, boolean failed) {
        Notification.Builder builder = new Notification.Builder(this, CHANNEL)
                .setSmallIcon(failed ? android.R.drawable.stat_notify_error : android.R.drawable.stat_sys_upload_done)
                .setContentTitle(failed ? "DeckyShare transfer failed" : "DeckyShare transfer complete")
                .setContentText(message)
                .setAutoCancel(true)
                .setColor(failed ? Color.rgb(255, 120, 120) : Color.rgb(102, 192, 244));
        getSystemService(NotificationManager.class).notify(NOTIFICATION_ID, builder.build());
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    @Override public void onDestroy() {
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
