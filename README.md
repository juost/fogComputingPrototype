# Fog Computing Prototype

This repository contains a prototype for the TU Berlin course Fog Computing. 
The prototype creates, collects, visualizes and synchronizes sensor data between a client and a server.

## Requirements

- Python 3.12 (for native execution)
- Docker (for containerized execution)
- PyQt5 (for Matplotlib backend)

## Installation

### Clone the Repository

```bash
git clone git@github.com:juost/fogComputingPrototype.git
cd fogComputingPrototype
```
### Install Dependencies

```bash
pip install -r requirements.txt
sudo apt install python3-pyqt5
```

## Running the Project

### Running with Python

1. **Start the Server**

   Navigate to the server directory and start the server:

   ```bash
   cd server
   python server_main.py
   ```
   
2. **Generate the Client (only required initially and on api changes)**

    Ensure the server is running and then generate the client using the OpenAPI specification exposed by the server.
    Execute the following command in a new terminal in the root directory of the project:
    ```bash
    openapi-python-client generate --url http://<server-ip>:8000/openapi.json --output-path client/generated
    ```

3. **Start the Client**

   Navigate to the client directory and start the client:

   ```bash
   cd client
   python client_main.py --server-ip <server-ip>
   ```

### Running with Docker

1. **Build and Start the Server**

   ```bash
   docker-compose up --build fog_computing_server
   ```

2. **Generate the Client (only required initially and on api changes)**

    Ensure the server is running and then generate the client using the OpenAPI specification exposed by the server.
    Execute the following command in a new terminal in the root directory of the project:
    ```bash
    openapi-python-client generate --url http://<server-ip>:8000/openapi.json --output-path client/generated
    ```

3. **Build and Start the Client**
   > [!CAUTION]
   > Does not work since the ui for the client was intorduced, please use the native version instead

   The client can be run using Docker but without a UI:

   ```bash
   docker-compose up --build fog_computing_client
   ```

## Project Structure

- `server`: Contains the server code and server sided visualization.
- `client`: Contains the client code with data generation and visualization.
- `client/generated`: The generated client code from the OpenAPI specification.

## OpenAPI Documentation
The OpenAPI documentation for the server APIs can be accessed at the following URL:

   ```bash
   http://<server-ip>:8000/docs
   ```


## Notes

- Ensure that the server is running before generating the client and starting the client.
- The project assumes the use of UTC for all datetime operations to avoid timezone discrepancies.
