#!/usr/bin/env bash
set -euo pipefail

aosp_root=${1:-/work/src/ubox10-a16-ceiling}
tag=android-security-16.0.0_r7

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

expect_commit() {
    local project=$1
    local expected=$2
    local actual
    actual=$(git -C "$aosp_root/$project" rev-parse "${tag}^{}" 2>/dev/null) || \
        fail "$project does not have $tag; fetch the official tag object"
    [[ $actual == "$expected" ]] || fail "$project: expected $expected, got $actual"
}

expect_tree() {
    local project=$1
    local expected=$2
    local actual
    actual=$(git -C "$aosp_root/$project" rev-parse "${tag}^{tree}" 2>/dev/null) || \
        fail "$project does not have a tree for $tag"
    [[ $actual == "$expected" ]] || fail "$project: expected tree $expected, got $actual"
}

expect_blob_sha256() {
    local project=$1
    local path=$2
    local expected=$3
    local actual
    actual=$(git -C "$aosp_root/$project" show "$tag:$path" | sha256sum | cut -d' ' -f1)
    [[ $actual == "$expected" ]] || fail "$project/$path: expected $expected, got $actual"
}

expect_blob_text() {
    local project=$1
    local path=$2
    local expected=$3
    git -C "$aosp_root/$project" show "$tag:$path" | grep -Fq "$expected" || \
        fail "$project/$path does not contain expected text: $expected"
}

expect_commit .repo/manifests ebea28d151539ecf0730b1a4ab92ac33edc17ac9
expect_tree .repo/manifests e4641ccf8e59e0028248d32e5a7fd212760b7a22
expect_commit build/make e780ae328060afca5ed007c34322bfa7ce9b4e60
expect_commit build/release ecaf883f0ecb92307aa38fd98bf79029b5855565
expect_commit build/soong 4e8a4d55b99fce2bacf24b4942abf13d6cda2e12
expect_commit packages/modules/Connectivity 5276e77d46a4e1f3121f7d2f651fc2185fa59342
expect_commit packages/modules/UprobeStats 29fd11c92ed630721f946cf0ba57d80d11053b8d
expect_commit system/netd 68859d33e9bfe9ddb1afdc282905c63339c1928d
expect_commit system/bpf 4447acd742bf443f9088c300bd69f96ede8eaeb1
expect_commit system/bpfprogs cdb14b57cc698975b796224c507b4d15698b4788
expect_commit system/core 68be0c2c0006a0740d0b1809abe4717308f90d15
expect_commit system/apex 4c600506b4aceb0bb9f61bac84e9884d4b4d9b2b
expect_commit system/sepolicy d4a7f392598cee96d9479a8ac0f84259c19b043a
expect_commit system/linkerconfig e6e748db0343684959fc49356f07e1793f96db85
expect_commit system/libvintf 2ef218d3586bbef90c2f0c14bbda901c7d60460a
expect_commit system/incremental_delivery c999e3e207ec7633a172d773dda162746b6eaf18
expect_commit hardware/interfaces b553275c84253b074a8532a6ff0f4406c43e606e
expect_commit kernel/configs e90ea709c3c2ec34bcfd7dca2ebec0bae287c91f
expect_commit device/google/atv 28ec82d1e4f13072eb978f3e74335195aa7dfcc4
expect_commit device/generic/armv7-a-neon 5be6c1b1d84a1f046329176d5da3368cb6547703
expect_commit frameworks/base 0e92b8431dbcc5bc65dafc485fc0cef277df0644
expect_commit prebuilts/vndk/v31 1a059a5a203352d3e0c2fd3ccff5719cc37fc340

expect_blob_sha256 .repo/manifests default.xml 455b978ffd07e7a1699364e6ccac3f8b9fe455905712b4923c0b97414f97769d
expect_blob_sha256 build/make core/build_id.mk 5c700904da9d04898ebe031a4fc8d6c252f17f4ef30a48b92ee8aa5052128f54
expect_blob_sha256 packages/modules/Connectivity bpf/loader/NetBpfLoad.cpp 03d6adf9bf499cc23ef170dafa23a86c8a5ecb1e2c182dea940c0cdfba650254
expect_blob_sha256 packages/modules/Connectivity bpf/loader/netbpfload.rc b084ef36f4410b92ebf71ba6644baa989b84267b0d773661ecaebb7ea5a3c270
expect_blob_sha256 system/netd tests/kernel_test.cpp 6be1db941ba6d0bf83b4e6bb1d6e7376bc66d629110fdf2f93f18e6b97641697
expect_blob_sha256 system/core libprocessgroup/profiles/cgroups.json ab2ed667ff45958843fb0c6ee953a5512def0ae87470c4358aa9576a6a4b2e22
expect_blob_sha256 system/core libprocessgroup/profiles/task_profiles.json bee4c6181381d3e41c115475abcc3962e809a6fc2a97276e14c23db85e3e2ec9
expect_blob_sha256 system/core rootdir/init.rc 133923deca1bb776b83856eba406441849fb1903f8aa2f96940183ae976e205d
expect_blob_sha256 system/apex apexd/apexd.cpp dd46d97231b5e1611f0d659573ea7303a74e34c14f2948fbb06da424c3615300
expect_blob_sha256 hardware/interfaces compatibility_matrices/compatibility_matrix.6.xml 3cb61405c9d65d5f2e428ff24556668d497a83b7330e711520c7a6661d2a3262
expect_blob_sha256 system/sepolicy private/genfs_contexts 8631ad087da5e4e2e81ce3a179b9d9ddf31532e9f4d3b6de32bd6d177512f3f1
expect_blob_sha256 device/google/atv products/gsi_tv_base.mk 8ac914ec861407aafc11030a140358883f43ec93f31b1b6c1aad4378c9efc035
expect_blob_sha256 kernel/configs s/android-5.4/android-base.config 26ea5c3c19e3547e8d1a74415c60e6ab2678230488d26baeb8aa9f07f905676f
expect_blob_sha256 system/incremental_delivery incfs/incfs.cpp c5fbf935b1f6b2cd5e2fdafe0327c132ab83666e6344b0b5137244e377c4e1e8

git -C "$aosp_root/build/make" show "$tag:core/build_id.mk" | \
    grep -qx 'BUILD_ID=BP2A.250805.034' || fail "unexpected r7 BUILD_ID"
expect_blob_text build/release release_config_map.textproto 'target: "bp2a"'
expect_blob_text build/release release_configs/bp2a.textproto 'inherits: "bp1a"'
expect_blob_text build/release flag_values/bp2a/RELEASE_PLATFORM_SDK_VERSION.textproto 'string_value: "36"'
expect_blob_text build/release flag_values/bp2a/RELEASE_PLATFORM_SDK_VERSION_FULL.textproto 'string_value: "36.0"'
expect_blob_text build/release flag_values/bp2a/RELEASE_PLATFORM_VERSION_CODENAME.textproto 'string_value:  "REL"'
expect_blob_text build/release flag_values/bp2a/RELEASE_PLATFORM_VERSION_LAST_STABLE.textproto 'string_value:  "16"'
expect_blob_text build/release flag_values/bp2a/RELEASE_PLATFORM_SECURITY_PATCH.textproto 'string_value: "2025-08-05"'
expect_blob_text build/release flag_values/bp2a/RELEASE_AVF_ENABLE_EARLY_VM.textproto 'bool_value: true'
expect_blob_text kernel/configs s/android-5.4/android-base.config '# CONFIG_NFS_FS is not set'

echo "PASS: exact android-security-16.0.0_r7 audit identities verified"
