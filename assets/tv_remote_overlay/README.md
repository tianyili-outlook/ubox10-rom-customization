# UBOX10 TV Remote framework overlay

This static Runtime Resource Overlay changes only
`android:string/config_tvRemoteServicePackage`, from the empty value in the
X12 Android 12 framework to:

```text
com.google.android.tv.remote.service
```

The APK is built locally with Android Build Tools 31 and signed with the
repository's existing test key. Only the source and public certificate belong
in Git; generated APKs remain under `work/`.
