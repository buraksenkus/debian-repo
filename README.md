# Debian Repository Creator

This Python program helps to create your own Debian package repository and serve it on authenticated HTTP server.

## Features

* Watching pool directories & automatic package registry update.
* Running as Linux service.
* Basic HTTP authentication with username and password.
* Connection guide creation.
* **SOON:** Backing up existing packages.

## Creating & Serving Debian Repository

* Install dependencies

    ```shell
    apt install dpkg-dev -y
    pip install pyinotify pyasyncore
    ```

* Create a configuration file `config.json` in project directory. Architectures and distributions can be changed.

    ```json
    {
        "architectures": ["amd64", "armhf", "arm64"],
        "dists": ["focal", "jammy", "noble"],
        "short_name": "repo_name",
        "description": "Your repository description",
        "email": "your_email@domain.com",
        "name": "Your Name",
        "port": 8645,
        "auth": "basic",
        "users": {
            "username1": "password1",
            "username2": "password2"
        }
    }
    ```

    Available options:
    * **auth**: *basic, none*

* Run repository script by specifying configuration file.

    ```shell
    ./debianrepo.py -c config.json
    ```

* Add your debian packages into `pool` folders based on architecture and distro.

## Using Debian Repository

When you start the repository server, `CONNECTION_GUIDE.md` file will be created. You can see connection instructions in this file.
