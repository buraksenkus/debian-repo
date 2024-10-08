import subprocess

def execute_cmd(cmd, env=None):
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    out, err = process.communicate()
    return out, err, process.returncode
