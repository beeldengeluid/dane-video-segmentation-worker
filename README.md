[![main branch](https://github.com/beeldengeluid/dane-video-segmentation-worker/actions/workflows/main-branch.yml/badge.svg)](https://github.com/beeldengeluid/dane-video-segmentation-worker/actions/workflows/main-branch.yml)

# dane-video-segmentation-worker

Running Scenedetect to detect shots and select keyframes.
Including code for extracting the keyframes too.
Extracting audio and generating spectrograms are legacy options and might not work well anymore. 


## Installation

Use Poetry to install this project into a virtualenv.

```sh
poetry install
```

Installing `python-opencv` in a virtualenv, and thus not as a system package, could cause certain shared-objects to be missing. So far it seems libgl1 might be missing this way. Install it using:

```
apt-get install libgl1
```

To make sure the unit-test work as well

```
apt-get install ffmpeg
```


## Run in local Python virtualenv

For local testing, make sure to put a config.yml in the root of this repo:

```
cp ./config/config.yml config.yml
```

Then make sure to activate your virtual environment:

```sh
poetry shell
```

Then run `./scripts/check-project.sh` to:

- linting (Using `flake8`)
- type checking (Using `mypy`)
- unit testing (Using `pytest`)

## Run test file in local Docker Engine

This form of testing/running avoids connecting to DANE:

- No connection to DANE RabbitMQ is made
- No connection to DANE ElasticSearch is made

This is ideal for testing:

- main_data_processor.py, which uses `VISXP_PREP.TEST_INPUT_FILE` (see config.yml) to produce this worker's output
- I/O steps taken after the output is generated, i.e. deletion of input/output and transfer of output to S3

```sh
docker build -t dane-video-segmentation-worker .
```

Check out the `docker-compose.yml` to learn about how the main process is started. As you can see there are two volumes mounted and an environment file is loaded:

```yml
version: '3'
services:
  web:
    image: dane-video-segmentation-worker:latest  # your locally built docker image
    volumes:
      - ./data:/data  # put input files in ./data and update VISXP_PREP.TEST_INPUT_FILE in ./config/config.yml
      - ./config:/root/.DANE  # ./config/config.yml is mounted to configure the main process
    container_name: visxp
    command: --run-test-file  # NOTE: comment this line to spin up th worker
    env_file:
      - s3-creds.env  # create this file with AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to allow boto3 to connect to your AWS S3 bucket (see OUTPUT.S3_* variables in config.yml)
    logging:
      options:
        max-size: 20m
    restart: unless-stopped
```

There is no need to update the docker-compose.yml, but make sure to:

- adapt `./config/config.yml` (see next sub-section for details)
- create `s3-creds.env` to allow the worker to upload output to your AWS S3 bucket

### Config

The following parts are relevant for local testing (without connecting to DANE). All defaults
are fine for testing, except:

- `VISXP_PREP.TEST_INPUT_FILE`: make sure to supply your own `mp4` file in ./data
- `S3_ENDPOINT_URL`: ask your DANE admin for the endpoint URL
- `S3_BUCKET`: ask your DANE admin for the bucket name

```yml
FILE_SYSTEM:
    BASE_MOUNT: /data
    INPUT_DIR: input-files
    OUTPUT_DIR: output-files/visxp_prep
PATHS:
    TEMP_FOLDER: /data/input-files
    OUT_FOLDER: /data/output-files
VISXP_PREP:
    RUN_KEYFRAME_EXTRACTION: true
    RUN_AUDIO_EXTRACTION: false
    SPECTROGRAM_WINDOW_SIZE_MS: 1000
    SPECTROGRAM_SAMPLERATE_HZ:
        - 24000
    TEST_INPUT_FILE: /data/testob-take-2.mp4
INPUT:
    DELETE_ON_COMPLETION: False  # NOTE: set to True in production environment
OUTPUT:
    DELETE_ON_COMPLETION: False  # NOTE: set to True in production environment
    TAR_OUTPUT: false
    TRANSFER_ON_COMPLETION: True
    S3_ENDPOINT_URL: https://your-s3-host/
    S3_BUCKET: your-s3-bucket  # bucket reserved for 1 type of output
    S3_FOLDER_IN_BUCKET: assets  # folder within the bucket
```

## Relevant links

Also see:
https://stackoverflow.com/questions/64664094/i-cannot-use-opencv2-and-received-importerror-libgl-so-1-cannot-open-shared-obj

https://docs.opencv.org/4.x/d2/de6/tutorial_py_setup_in_ubuntu.html
