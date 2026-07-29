package com.ubox10.m8;

import android.app.Activity;
import android.os.Bundle;

public final class DrmProbeActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        DrmProbe.run(getIntent().getStringExtra("run_id"));
        finishAndRemoveTask();
    }
}
