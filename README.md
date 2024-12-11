# Portland Weather Data Pipeline

This project processes weather data from Portland, Oregon. It utilizes Airflow for scheduling and orchestration.

## Project Structure

The project is organized into several directories:

- `dags`: Contains the Airflow DAGs (Directed Acyclic Graphs) defining the data pipeline tasks.
- `logs`: Stores logs generated during the execution of the pipeline tasks.
- `config`: Contains configuration files for the pipeline.
- `airflow_env`: Directory containing Airflow environment setup.
- `UI`: Contains UI elements for the project.

## Key Files

- `docker-compose.yaml`: Defines the Docker Compose configuration for the project.
- `.gitignore`: Specifies files and directories to ignore during version control.
