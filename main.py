import sublime, sublime_plugin, os, time
import subprocess

settings = {}

STREAM_STDOUT = 1
STREAM_STDERR = 2
STREAM_BOTH = STREAM_STDOUT + STREAM_STDERR

def popen(cmd, stdout=None, stderr=None, output_stream=STREAM_BOTH, env=None, extra_env=None):
    """Open a pipe to an external process and return a Popen object."""

    info = None

    if os.name == 'nt':
        info = subprocess.STARTUPINFO()
        info.dwFlags |= subprocess.STARTF_USESTDHANDLES | subprocess.STARTF_USESHOWWINDOW
        info.wShowWindow = subprocess.SW_HIDE

    if output_stream == STREAM_BOTH:
        stdout = stdout or subprocess.PIPE
        stderr = stderr or subprocess.PIPE
    elif output_stream == STREAM_STDOUT:
        stdout = stdout or subprocess.PIPE
        stderr = subprocess.DEVNULL
    else:  # STREAM_STDERR
        stdout = subprocess.DEVNULL
        stderr = stderr or subprocess.PIPE

    if env is None:
        env = create_environment()

    if extra_env is not None:
        env.update(extra_env)

    try:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=stderr,
            startupinfo=info,
            env=env
        )
    except Exception as err:
        print(err)


def run_shell_cmd(cmd):
    """Run a shell command and return stdout."""
    proc = popen(cmd, env=os.environ)

    try:
        out, err = proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        out = b''
        print('shell timed out after {} seconds, executing {}'.format(timeout, cmd))

    return out

def extract_path(cmd, delim=':'):
    """Return the user's PATH as a colon-delimited list."""
    # print('user shell:', cmd[0])

    out = run_shell_cmd(cmd).decode()
    path = out.split('__SUBL_PATH__', 2)

    if len(path) > 1:
        path = path[1]
        return ':'.join(path.strip().split(delim))
    else:
        print('Could not parse shell PATH output:\n' + (out if out else '<empty>'))
        sublime.error_message(
            'SublimeLinter could not determine your shell PATH. '
            'It is unlikely that any linters will work. '
            '\n\n'
            'Please see the troubleshooting guide for info on how to debug PATH problems.')
        return ''


def get_shell_path(env):
    """
    Return the user's shell PATH using shell --login.

    This method is only used on Posix systems.

    """

    if 'SHELL' in env:
        shell_path = env['SHELL']
        shell = os.path.basename(shell_path)

        # We have to delimit the PATH output with markers because
        # text might be output during shell startup.
        if shell in ('bash', 'zsh'):
            return extract_path(
                (shell_path, '-l', '-c', 'echo "__SUBL_PATH__${PATH}__SUBL_PATH__"')
            )
        elif shell == 'fish':
            return extract_path(
                (shell_path, '-l', '-c', 'echo "__SUBL_PATH__"; for p in $PATH; echo $p; end; echo "__SUBL_PATH__"'),
                '\n'
            )
        else:
            print('Using an unsupported shell:', shell)

    # guess PATH if we haven't returned yet
    split = env['PATH'].split(':')
    p = env['PATH']

    for path in (
        '/usr/bin', '/usr/local/bin'
    ):
        if path not in split:
            p += (':' + path)

    return p

env = {}
env["PATH"] = get_shell_path(os.environ)

def plugin_loaded():
    global settings
    settings = sublime.load_settings("EslintFix.sublime-settings")

class EslintFixCommand(sublime_plugin.TextCommand):
    def run(self, edit):

        window = sublime.active_window()
        active_view = window.active_view()
        filename = active_view.file_name()
        eslint = os.path.join(window.folders()[0], "node_modules/.bin", "eslint")
        proc = popen((eslint, "--fix", filename), env=env)


