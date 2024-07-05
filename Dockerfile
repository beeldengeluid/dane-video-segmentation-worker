FROM docker.io/python:3.11

RUN apt-get clean && apt-get update -y && apt-get upgrade -y

RUN apt-get install -y libgl1 ffmpeg

RUN pip install --upgrade pip
RUN pip install poetry==1.5.1

# Create dirs for:
# - Injecting config.yml: /root/.DANE
# - Storing the source code: /src
# - Keeping IO: /data
RUN mkdir /root/.DANE /src /data

WORKDIR /src

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-ansi --without dev --no-root && rm -rf $POETRY_CACHE_DIR
COPY . /src

# create an objects dir in .git. This remains empty, only needs to be present for git rev to work
#RUN mkdir /src/.git/objects  

# Write provenance info about software versions to file
RUN echo "dane-video-segmentation-worker;https://github.com/beeldengeluid/dane-video-segmentation-worker/commit/$(git rev-parse HEAD)" >> /software_provenance.txt
RUN echo "scenedetect;$(poetry show scenedetect | grep ' version .*' | cut --delimiter=: --fields=2 | cut --delimiter=' ' --fields=2)" >> /software_provenance.txt

ENTRYPOINT ["./docker-entrypoint.sh"]
