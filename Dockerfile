FROM docker.io/python:3.11 AS req

RUN python3 -m pip install pipx && \
  python3 -m pipx ensurepath

RUN pipx install poetry==1.7.1 && \
  pipx inject poetry poetry-plugin-export 
  #&& \
  #pipx run poetry config warnings.export false

COPY ./poetry.lock ./poetry.lock
COPY ./pyproject.toml ./pyproject.toml
RUN pipx run poetry export --without-hashes --format requirements.txt --output requirements.txt

FROM docker.io/python:3.11

# Create dirs for:
# - Injecting config.yml: /root/.DANE
# - Mount point for input & output files: /data
# - Storing the source code: /src
RUN mkdir \
  /data \
  /model \
  /root/.DANE \
  /src

WORKDIR /src

COPY --from=req ./requirements.txt requirements.txt

RUN pip install --no-cache-dir -r requirements.txt
COPY ./ /src

# create an objects dir in .git. This remains empty, only needs to be present for git rev to work
#RUN mkdir /src/.git/objects  

# Write provenance info about software versions to file
RUN echo "dane-video-segmentation-worker;https://github.com/beeldengeluid/dane-video-segmentation-worker/commit/$(git rev-parse HEAD)" >> /software_provenance.txt
RUN echo "scenedetect;$(poetry show scenedetect | grep ' version .*' | cut --delimiter=: --fields=2 | cut --delimiter=' ' --fields=2)" >> /software_provenance.txt

ENTRYPOINT ["./docker-entrypoint.sh"]
