FROM docker.io/python:3.10

COPY ./ /src

WORKDIR /src

RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

CMD [ "python", "worker.py" ]