# check if fogComputingVenv exists
if [ ! -d "fogComputingVenv" ]; then
    echo "Creating virtual environment fogComputingVenv"
    python3 -m venv fogComputingVenv
fi

#activate the virtual environment
./fogComputingVenv/bin/activate

#check pip is installed
if ! [ -x "$(command -v pip)" ]; then
    echo "pip is not installed"
    exit 1
fi

#install the required packages
pip install -r requirements.txt

#generate client - exchange the url with the correct one if not running locally
openapi-python-client generate --url http://127.0.0.1:8000/openapi.json --output-path client/generated