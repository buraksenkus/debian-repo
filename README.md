# Debian Repository Creator

This Python program helps to create your own Debian package repository and serve it on authenticated HTTP server.

## Features

* Watching pool directories & automatic package registry update.
* Running as Linux service.
* Basic HTTP authentication with username and password.
* Connection guide creation.
* Backing up repository periodically.

## Creating & Serving Debian Repository

* Install dependencies

    ```shell
    apt install dpkg-dev -y
    pip install pyinotify pyasyncore
    ```

* Create a copy of `example_config.json` as `config.json` and make your changes.

    Available options:
    * **auth**: *basic, none*
    * **backup**:
      * **enable**: Enables/disables backup feature. It is false by default.
      * **format**: Backup format. Can be "zip", "tar" or "both".
      * **interval**: Backup interval in hours.
      * **copies**: Keeps last <copies> copies in backup folder. Removes older ones.

* Run repository script by specifying configuration file.

    ```shell
    ./debianrepo -c config.json
    ```

* Add your debian packages into `pool` folders based on architecture and distro.

## Using Debian Repository

When you start the repository server, `CONNECTION_GUIDE.md` file will be created. You can see connection instructions in this file.
