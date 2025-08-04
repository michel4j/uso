Deploying a USO instance
========================

1. From the top-level directory, run the command `prepare-instance.sh` as follows:

   ```bash
   
      ./deploy/prepare-instance.sh <deploy top-level directory>
   
   ```

2. This command will build a docker/podman image "usonline:latest" and create a barebones directory structure. Add any
   data you want to load into the `local/kickstart/` in either YAML or JSON format. The data should be in the format
   similar to that produced by the Django `dumpdata` command.

    If you want to generate fake data:
    
   ```bash
   
         ./deploy/generate-data.py <deploy top-level directory>/usonline/local
   
    ```

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

5. Access the USO site at http://localhost:8080. 