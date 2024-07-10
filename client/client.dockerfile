FROM ubuntu:latest

RUN apt-get update -y && apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3-pip \
    python3-pyqt5

WORKDIR /home/fog

# Copy the requirements.txt file into the container
COPY requirements.txt /home/fog/requirements.txt

# Create a virtual environment and install dependencies
RUN python3 -m venv /home/fog/fogComputingVenv && \
    /home/fog/fogComputingVenv/bin/pip install --upgrade pip && \
    /home/fog/fogComputingVenv/bin/pip install --break-system-packages -r /home/fog/requirements.txt

# Copy the rest of the application code
ENV PYTHONPATH="/home/fog"

# Set the entrypoint to use the virtual environment's Python interpreter
ENTRYPOINT ["/home/fog/fogComputingVenv/bin/python", "./client/client_main.py"]
