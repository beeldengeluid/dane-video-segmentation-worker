FROM docker.io/python:3.11

RUN apt-get clean && apt-get update -y && apt-get upgrade -y

RUN apt-get install -y libgl1 ffmpeg

RUN pip install --upgrade pip
RUN pip install scenedetect[opencv] --upgrade
RUN pip install poetry==1.5.1

# Create dirs for:
# - Injecting config.yml: /root/.DANE
# - Mount point for input & output files: /mnt/dane-fs
# - Storing the source code: /src
# - Storing the input file to be used while testing: /src/data
RUN mkdir /root/.DANE /mnt/dane-fs /src /data

WORKDIR /src

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache



COPY pyproject.toml poetry.lock ./
RUN poetry install --no-ansi --without dev --no-root && rm -rf $POETRY_CACHE_DIR

# Write provenance info about software versions to file
RUN echo "dane-video-segmentation-worker;https://github.com/beeldengeluid/dane-video-segmentation-worker/commit/$(git rev-parse HEAD)" >> /software_provenance.txt
RUN echo "scenedetect;$(poetry show scenedetect | grep ' version .*' | cut --delimiter=: --fields=2 | cut --delimiter=' ' --fields=2)" >> /software_provenance.txt

COPY . /src

ENTRYPOINT ["./docker-entrypoint.sh"]
