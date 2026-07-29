package com.ubox10.m8;

import android.media.MediaDrm;
import android.media.UnsupportedSchemeException;
import android.util.Log;

import java.util.UUID;

public final class DrmProbe {
    private static final String LOG_TAG = "M8DrmProbe";
    private static final UUID WIDEVINE =
            UUID.fromString("edef8ba9-79d6-4ace-a3c8-27dcd51d21ed");
    private static final UUID CLEARKEY =
            UUID.fromString("e2719d58-a985-b3c9-781a-b030af78d30e");
    private static String runId = "cli";

    private DrmProbe() {}

    private static void emit(String key, Object value) {
        String text = String.valueOf(value).replace('\n', ' ').replace('\r', ' ');
        String line = key + "=" + text;
        System.out.println(line);
        Log.i(LOG_TAG, runId + " " + line);
    }

    private static String property(MediaDrm drm, String name) {
        try {
            String value = drm.getPropertyString(name);
            return value == null || value.isEmpty() ? "<empty>" : value;
        } catch (RuntimeException error) {
            return "<" + error.getClass().getSimpleName() + ">";
        }
    }

    private static String hdcpLevel(int level) {
        switch (level) {
            case MediaDrm.HDCP_LEVEL_UNKNOWN:
                return "UNKNOWN";
            case MediaDrm.HDCP_NONE:
                return "NONE";
            case MediaDrm.HDCP_V1:
                return "V1";
            case MediaDrm.HDCP_V2:
                return "V2";
            case MediaDrm.HDCP_V2_1:
                return "V2_1";
            case MediaDrm.HDCP_V2_2:
                return "V2_2";
            case MediaDrm.HDCP_V2_3:
                return "V2_3";
            case MediaDrm.HDCP_NO_DIGITAL_OUTPUT:
                return "NO_DIGITAL_OUTPUT";
            default:
                return "VALUE_" + level;
        }
    }

    private static void probe(String label, UUID scheme) {
        boolean supported = MediaDrm.isCryptoSchemeSupported(scheme);
        emit(label + ".supported", supported);
        if (!supported) {
            return;
        }

        MediaDrm drm = null;
        try {
            drm = new MediaDrm(scheme);
            emit(label + ".opened", true);
            emit(label + ".vendor", property(drm, MediaDrm.PROPERTY_VENDOR));
            emit(label + ".version", property(drm, MediaDrm.PROPERTY_VERSION));
            emit(label + ".description", property(drm, MediaDrm.PROPERTY_DESCRIPTION));
            emit(label + ".algorithms", property(drm, MediaDrm.PROPERTY_ALGORITHMS));
            emit(label + ".securityLevel", property(drm, "securityLevel"));

            String systemId = property(drm, "systemId");
            emit(label + ".systemIdPresent",
                    !"<empty>".equals(systemId) && !systemId.startsWith("<"));

            emit(label + ".connectedHdcp", hdcpLevel(drm.getConnectedHdcpLevel()));
            emit(label + ".maxHdcp", hdcpLevel(drm.getMaxHdcpLevel()));
            emit(label + ".openSessions", drm.getOpenSessionCount());
            emit(label + ".maxSessions", drm.getMaxSessionCount());

            String[] mediaTypes = {"video/mp4", "video/webm", "audio/mp4"};
            for (String mediaType : mediaTypes) {
                emit(label + ".schemeSupports." + mediaType,
                        MediaDrm.isCryptoSchemeSupported(scheme, mediaType));
            }

            String[] codecTypes = {"video/avc", "video/hevc", "video/x-vnd.on2.vp9"};
            for (String codecType : codecTypes) {
                emit(label + ".requiresSecureDecoder." + codecType,
                        drm.requiresSecureDecoder(codecType));
            }
        } catch (UnsupportedSchemeException error) {
            emit(label + ".opened", false);
            emit(label + ".error", error.getClass().getSimpleName());
        } catch (RuntimeException error) {
            emit(label + ".opened", false);
            emit(label + ".error", error.getClass().getSimpleName());
        } finally {
            if (drm != null) {
                drm.release();
            }
        }
    }

    public static void run(String requestedRunId) {
        runId = requestedRunId == null || requestedRunId.isEmpty() ? "unknown" : requestedRunId;
        emit("schema", "ubox10.m8-drm-probe/v1");
        probe("widevine", WIDEVINE);
        probe("clearkey", CLEARKEY);
        emit("complete", true);
    }

    public static void main(String[] args) {
        run(args.length == 0 ? "cli" : args[0]);
    }
}
