Deploying a USO instance
========================

1. From the top-level directory, run the command `prepare-instance.sh` as follows:

   ```bash
   
      ./deploy/prepare-instance.sh <deploy top-level directory>
   
   ```

2. This command will build a docker/podman image "usonline:latest" and create a barebones directory structure. Add any
   data you want to load into the `local/kickstart/` in either YAML or JSON format. The data should be in the format
   similar to that produced by the Django `dumpdata` command.
3. Edit the docker-compose.yml file to reflect your deployment environment. Change the environment settings to create
   the appropriate database and uso admin accounts.
4. Run the docker-compose up command to start the database and USO. The database will be initialized with the data in
   the kickstart directory if provided.
   ```bash
       docker-compose up -d
   ```
   OR
   ```
       podman-compose up -d
   ```

5. Access the USO site at http://localhost. The default admin account is `admin` with password `usoadmin` unless you
   changed the value in `docker-compose.yml`.
6. Copy the cronjob file `usonline.crotasks` to the appropriate location on the host system to run the cron job every 10
   minutes.
7. Logos are needed in a few places. To customize the logo, place two PNG files in the `local/media/logos` directory
   named `logo-horiz.png` (300 x 90, logo) and `logo-oriz-white.png` (White version for dark backgrounds).
8. By default, Profile photos for users should be placed in the `local/media/idphoto/<username>.jpg` for each user.
   Alternatively, they can be fetched from a remote server through the Profile manager. See RemoteProfileManager for an
   example. The photo should be minimum 200 x 200 pixels.