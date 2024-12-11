from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
import json 
from airflow.providers.postgres.hooks.postgres import PostgresHook
import requests
import psycopg2
from airflow.hooks.base_hook import BaseHook

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': days_ago(1),
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# Initialize the DAG
dag = DAG(
    'weather_data_pipeline',
    default_args=default_args,
    description='A simple weather data pipeline using Airflow',
    schedule_interval='@daily',  # Run the DAG daily
    catchup=False,
)

# Define the API key and base URL
API_KEY = 'dd24fafbe11ff5c183032972a933481d'
BASE_URL = 'https://api.openweathermap.org/data/2.5/weather'

# Define the HttpSensor task to check if the API is online
# api_check_task = HttpSensor(
#     task_id='check_api_online',
#     http_conn_id='open_weather_api',
#     endpoint=f'{BASE_URL}?q=Portland&appid={API_KEY}',
#     request_params={},
#     response_check=lambda response: response.status_code == 200,
#     poke_interval=5,
#     timeout=60,
#     mode='reschedule',  # Allows the sensor to release the worker slot while waiting

#     dag=dag,
# )

# Define the SimpleHttpOperator task to fetch the weather data
# fetch_weather_task = SimpleHttpOperator(
#     task_id='fetch_weather_data',
#     method='GET',
#     http_conn_id='open_weather_api',
#     endpoint=f'{BASE_URL}?q=Portland&appid={API_KEY}',
#     response_filter=lambda response: (
#         response.json() if response.status_code == 200 
#         else response.raise_for_status()
#     ),
#     log_response=True,  # Log the response for debugging
#     dag=dag,
# )

# Define a function that uses requests to check the API status
def check_api_online():
    """
    Checks if the OpenWeatherMap API is online by sending a GET request.

    Returns:
        bool: True if the API is online (HTTP status code 200), False otherwise.
    """
    response = requests.get(f'{BASE_URL}?q=Portland&appid={API_KEY}')
    
    # If the response is successful (status code 200), return True
    if response.status_code == 200:
        print("API is online.")
        return True
    else:
        print(f"Failed to reach API. Status code: {response.status_code}")
        return False

# Define the PythonOperator task to check if the API is online
check_api_online = PythonOperator(
    task_id='check_api_online',
    python_callable=check_api_online,
    dag=dag,
)

# Define the function to fetch the weather data using requests
def fetch_weather_data():
    """
    Fetches the weather data from the OpenWeatherMap API.

    Returns:
        dict: The weather data in JSON format.

    Raises:
        Exception: If the API request fails.
    """
    response = requests.get(f'{BASE_URL}?q=Portland&appid={API_KEY}')
    if response.status_code == 200:
        weather_data = response.json()
        return weather_data
    else:
        raise Exception(f"Failed to fetch weather data. Status code: {response.status_code}")

# Define the PythonOperator task to fetch the weather data
fetch_weather_data = PythonOperator(
    task_id='fetch_weather_data',
    python_callable=fetch_weather_data,
    dag=dag,
)

from datetime import datetime, timedelta


def transform_data(ti):
        """
        Transforms the weather data from the API into a more suitable format and pushes it to XCom.

        The transformation includes:

        - Converting temperature from Kelvin to Fahrenheit
        - Extracting the city name, pressure, humidity, and timestamp from the API response

        The transformed data is then pushed to XCom with the key "p_weather_data".
        """
        weather_data = ti.xcom_pull(key="p_weather_data", task_ids='fetch_weather_data')
        city = weather_data['name']
        temperature_k = weather_data['main']['temp']

        # Transforming temperature to Fahrenheit
        temperature_f = (temperature_k - 273.15) * 9/5 + 32
        pressure = weather_data['main']['pressure']
        humidity = weather_data['main']['humidity']
        timestamp = datetime.fromtimestamp(weather_data['dt'], timezone.utc)
        portland_weather_data = {
            'city': city,   
            'temperature': temperature_f,
            'pressure': pressure,
            'humidity': humidity,
            'timestamp': timestamp,
        }

        ti.xcom_push(key="p_weather_data", value=portland_weather_data)
        return portland_weather_data

transform_weather_data = PythonOperator(
        task_id='transform_weather_data',
        python_callable=transform_data,
        dag=dag,
)


load_weather_task = PostgresOperator(
    task_id='load_weather_data',
    postgres_conn_id='portland_data',
    sql=""" 
        CREATE TABLE IF NOT EXISTS daily_weather (
            city VARCHAR(255),
            temperature DECIMAL(10, 2),
            pressure DECIMAL(10, 2),
            humidity DECIMAL(10, 2),
            timestamp TIMESTAMP
        );

        INSERT INTO daily_weather (city, temperature, pressure, humidity, timestamp)
        VALUES (
            %(city)s,
            %(temperature)s,
            %(pressure)s,
            %(humidity)s,
            %(timestamp)s
        );
    """,
    parameters={
        'city': "{{ (ti.xcom_pull(task_ids='transform_weather_data', key='p_weather_data') or {}).get('city', '') }}",
        'temperature': "{{ (ti.xcom_pull(task_ids='transform_weather_data', key='p_weather_data') or {}).get('temperature', 0) }}",
        'pressure': "{{ (ti.xcom_pull(task_ids='transform_weather_data', key='p_weather_data') or {}).get('pressure', 0) }}",
        'humidity': "{{ (ti.xcom_pull(task_ids='transform_weather_data', key='p_weather_data') or {}).get('humidity', 0) }}",
        'timestamp': "{{ (ti.xcom_pull(task_ids='transform_weather_data', key='p_weather_data') or {}).get('timestamp','1970-01-01 00:00:00') }}",
    },
    dag=dag,
)

# Set up the task dependencies
check_api_online >> fetch_weather_data >> transform_weather_data >> load_weather_task
