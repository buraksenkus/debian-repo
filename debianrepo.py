#!/usr/bin/python3

import argparse
import json
import os
from repository import DebianRepository

if not os.path.exists("/usr/bin/dpkg-scanpackages"):
    raise Exception("Please install dpkg-dev package.")

root_dir = os.path.dirname(os.path.realpath(__file__))
repo_dir = os.path.join(root_dir, "repo")


parser = argparse.ArgumentParser(
                    prog='debianrepo.py',
                    description='Debian repository controller')

parser.add_argument('-c', '--config', required=True, help="Configuration file")
parser.add_argument('-k', '--keyring', action='store_true', help="just generate GPG key without running server")
parser.add_argument('-s', '--service', action='store_true', help="just create and start a Linux service")
parser.add_argument('-r', '--remove-service', action='store_true', help="just stop and remove Linux service")
parser.add_argument('--no-watch', default=False, action='store_true', help="watch changes in pool directories")

args = parser.parse_args()

with open(args.config) as config_file:
    conf = json.load(config_file)

repository = DebianRepository(config=conf, dir=repo_dir, no_watch=args.no_watch)
    
if args.service:
    if args.remove_service:
        print("Don't use --remove-service and --service flags at the same time!")
        exit(1)
    repository.create_service(args.config)
    exit(0)
    
if args.remove_service:
    repository.remove_service(args.config)
    exit(0)
    
if args.keyring:
    repository.generate_gpg()
    exit(0)

repository.start()
