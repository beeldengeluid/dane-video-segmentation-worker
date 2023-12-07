FROM docker.io/python:3.10

RUN apt-get clean && apt-get update -y && apt-get upgrade -y

RUN apt-get install -y libgl1 ffmpeg


# Create dirs for:
# - Injecting config.yml: /root/.DANE
# - Mount point for input & output files: /mnt/dane-fs
# - Storing the source code: /src
RUN mkdir /root/.DANE /mnt/dane-fs /src

COPY ./requirements.txt /src

WORKDIR /src

# copy the pyproject file and install all the dependencies first
RUN pip install --upgrade pip
RUN pip install scenedetect[opencv] --upgrade
RUN pip install -r requirements.txt

COPY ./ /src


ENTRYPOINT ["./docker-entrypoint.sh"]