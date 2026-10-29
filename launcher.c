/*
 * VanishCam.app main executable.
 *
 * macOS only shows the camera permission pop-up for a real (compiled) app
 * process. If the app's main executable were a shell script, the request
 * would come from /bin/bash and macOS would silently ignore it.
 *
 * So this tiny program stays alive as "VanishCam" and runs
 * Contents/Resources/launch.sh as its child. The child (and the Python
 * process it starts) inherits VanishCam as the "responsible" app, so the
 * pop-up says "VanishCam would like to access the camera".
 *
 * Built by "Install VanishCam.command" with:  cc -O2 -o VanishCam launcher.c
 */
#include <libgen.h>
#include <errno.h>
#include <limits.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

extern char **environ;
static pid_t child = 0;

static void forward(int sig) {
    if (child > 0) kill(child, sig);
}

static int executable_path(char *out, size_t size) {
#ifdef __APPLE__
    char raw[PATH_MAX];
    uint32_t raw_size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &raw_size) != 0) return -1;
    return realpath(raw, out) ? 0 : -1;
#else
    ssize_t n = readlink("/proc/self/exe", out, size - 1);
    if (n < 0) return -1;
    out[n] = '\0';
    return 0;
#endif
}

int main(int argc, char *argv[]) {
    char exe[PATH_MAX];
    if (executable_path(exe, sizeof(exe)) != 0) return 1;
    char script[PATH_MAX];
    snprintf(script, sizeof(script), "%s/../Resources/launch.sh", dirname(exe));

    char **args = calloc((size_t)argc + 2, sizeof(char *));
    if (!args) return 1;
    int n = 0;
    args[n++] = "/bin/bash";
    args[n++] = script;
    for (int i = 1; i < argc; i++) {
        if (strncmp(argv[i], "-psn_", 5) == 0) continue;  /* old Finder argument */
        args[n++] = argv[i];
    }
    args[n] = NULL;

    signal(SIGTERM, forward);
    signal(SIGINT, forward);
    signal(SIGHUP, forward);

    if (posix_spawn(&child, "/bin/bash", NULL, NULL, args, environ) != 0) {
        perror("VanishCam: could not start launch.sh");
        return 1;
    }
    int status = 0;
    while (waitpid(child, &status, 0) < 0) {
        if (errno != EINTR) return 1;  /* retry only if interrupted by a signal */
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
