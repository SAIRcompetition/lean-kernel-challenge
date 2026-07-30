#include <lean/lean.h>

#if defined(__linux__)
#include <errno.h>
#include <linux/prctl.h>
#include <stdio.h>
#include <string.h>
#include <sys/prctl.h>
#endif

/*
 * `perf stat -D -1` creates disabled events on the timer process. These two
 * synchronous calls make only the declaration replay visible to those events.
 * On non-Linux development hosts there is no PMU contract, so the controls are
 * intentional no-ops and Main.lean still reports its internal monotonic time.
 */
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
    if (prctl(PR_TASK_PERF_EVENTS_ENABLE, 0, 0, 0, 0) != 0) {
        return perf_control_error("enable");
    }
#endif
    return lean_io_result_mk_ok(lean_box(0));
}

LEAN_EXPORT lean_obj_res lean_kernel_timer_perf_disable(void) {
#if defined(__linux__)
    if (prctl(PR_TASK_PERF_EVENTS_DISABLE, 0, 0, 0, 0) != 0) {
        return perf_control_error("disable");
    }
#endif
    return lean_io_result_mk_ok(lean_box(0));
}
