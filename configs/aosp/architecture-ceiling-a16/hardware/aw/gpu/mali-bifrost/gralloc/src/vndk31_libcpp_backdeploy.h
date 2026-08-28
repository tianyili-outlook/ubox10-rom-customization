/*
 * The retained API-31 vendor namespace resolves libc++ from the VNDK 31 APEX.
 * Android 16 libc++ headers otherwise emit a dependency on the newer
 * std::__libcpp_verbose_abort symbol.  libc++ explicitly permits callers to
 * override this fatal-only hook for back deployment.
 */
#pragma once

#if defined(__aarch64__) && !defined(_LIBCPP_VERBOSE_ABORT)
#define _LIBCPP_VERBOSE_ABORT(...) __builtin_abort()
#endif
