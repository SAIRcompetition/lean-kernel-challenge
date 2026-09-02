#include <lean/lean.h>

#if defined(__linux__)
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/syscall.h>
#include <linux/perf_event.h>
#include <asm/unistd.h>

/* The timer manages its own hardware instruction counter directly via
 * perf_event_open + ioctl(ENABLE/DISABLE) — the same mechanism KTP/3 uses,
 * verified to count inside the sealed judge container. It replaces the earlier
 * `perf stat -D -1` + prctl(PR_TASK_PERF_EVENTS_ENABLE) scheme: prctl only
 * enables counters the calling task itself created, so it never armed the
 * perf-owned counters and every replay came back <not counted> on this kernel.
 * The timer creates a counter it owns, so its own ENABLE/DISABLE take effect. */
static int perf_fd = -1;
static unsigned long long perf_last_count = 0;
#endif

static lean_obj_res perf_control_error(const char *operation) {
#if defined(__linux__)
    char message[256];
    int error_number = errno;
    (void)snprintf(
        message,
        sizeof(message),
        "cannot %s kernel timing PMU events: %s",
        operation,
        strerror(error_number));
    return lean_io_result_mk_error(lean_mk_io_user_error(lean_mk_string(message)));
#else
    (void)operation;
    return lean_io_result_mk_ok(lean_box(0));
#endif
}

LEAN_EXPORT lean_obj_res lean_kernel_timer_perf_enable(void) {
#if defined(__linux__)
    struct perf_event_attr attr;
    memset(&attr, 0, sizeof(attr));
    attr.type = PERF_TYPE_HARDWARE;
    attr.size = sizeof(attr);
    attr.config = PERF_COUNT_HW_INSTRUCTIONS;
    attr.disabled = 1;      /* created disabled; enabled around the replay only */
    attr.exclude_hv = 1;    /* full user+kernel scope, matching the sealed contract */
    perf_last_count = 0;
    perf_fd = (int)syscall(__NR_perf_event_open, &attr, 0 /*self*/, -1 /*any cpu*/, -1, 0);
    if (perf_fd < 0) {
        return perf_control_error("open");
    }
    if (ioctl(perf_fd, PERF_EVENT_IOC_RESET, 0) != 0 ||
        ioctl(perf_fd, PERF_EVENT_IOC_ENABLE, 0) != 0) {
        int saved = errno;
        close(perf_fd);
        perf_fd = -1;
        errno = saved;
        return perf_control_error("enable");
    }
#endif
    return lean_io_result_mk_ok(lean_box(0));
}

LEAN_EXPORT lean_obj_res lean_kernel_timer_perf_disable(void) {
#if defined(__linux__)
    if (perf_fd >= 0) {
        if (ioctl(perf_fd, PERF_EVENT_IOC_DISABLE, 0) != 0) {
            int saved = errno;
            close(perf_fd);
            perf_fd = -1;
            errno = saved;
            return perf_control_error("disable");
        }
        unsigned long long count = 0;
        ssize_t got = read(perf_fd, &count, sizeof(count));
        close(perf_fd);
        perf_fd = -1;
        if (got != (ssize_t)sizeof(count)) {
            return perf_control_error("read");
        }
        perf_last_count = count;
    }
#endif
    return lean_io_result_mk_ok(lean_box(0));
}

/* The last replay's instruction count as a decimal string. A string keeps the
 * full 64-bit range across the FFI boundary without box-width assumptions; the
 * judge parses it back to an integer. */
LEAN_EXPORT lean_obj_res lean_kernel_timer_perf_instructions(void) {
#if defined(__linux__)
    char buffer[32];
    (void)snprintf(buffer, sizeof(buffer), "%llu", perf_last_count);
    return lean_io_result_mk_ok(lean_mk_string(buffer));
#else
    return lean_io_result_mk_ok(lean_mk_string("0"));
#endif
}
