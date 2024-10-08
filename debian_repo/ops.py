import os
import subprocess


def do_hash(hash_name, hash_cmd, dist_path):
    hashes = []
    for root, _, files in os.walk(dist_path):
        for f in files:
            filepath = os.path.join(root, f)
            if f != "Release":
                filehash = subprocess.getoutput(f"{hash_cmd} {filepath}").split()[0]
                filesize = os.path.getsize(filepath)
                hashes.append(f" {filehash} {filesize} {os.path.relpath(filepath, dist_path)}")
    return "\n".join([f"{hash_name}:"] + hashes)