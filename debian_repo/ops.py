import os
import hashlib
from concurrent.futures import ThreadPoolExecutor

def calculate_hashes(dist_path):
    """
    Calculates MD5, SHA1, and SHA256 hashes for all files in a directory.
    """
    hashes = {
        "MD5Sum": [],
        "SHA1": [],
        "SHA256": []
    }

    def hash_file(filepath):
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest(), os.path.getsize(filepath)

    files_to_hash = []
    for root, _, files in os.walk(dist_path):
        for f in files:
            if f != "Release" and not f.endswith(".gpg") and not f.endswith("InRelease"):
                files_to_hash.append(os.path.join(root, f))

    with ThreadPoolExecutor() as executor:
        results = executor.map(hash_file, files_to_hash)

    for filepath, (md5_hex, sha1_hex, sha256_hex, filesize) in zip(files_to_hash, results):
        rel_path = os.path.relpath(filepath, dist_path)
        hashes["MD5Sum"].append(f" {md5_hex} {filesize} {rel_path}")
        hashes["SHA1"].append(f" {sha1_hex} {filesize} {rel_path}")
        hashes["SHA256"].append(f" {sha256_hex} {filesize} {rel_path}")

    return (
        "\\n".join([f"MD5Sum:"] + hashes["MD5Sum"]),
        "\\n".join([f"SHA1:"] + hashes["SHA1"]),
        "\\n".join([f"SHA256:"] + hashes["SHA256"])
    )
