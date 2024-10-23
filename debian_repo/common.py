import subprocess

def execute_cmd(cmd, env=None, cwd=None):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=cwd)
    out, err = process.communicate()
    return out, err, process.returncode
