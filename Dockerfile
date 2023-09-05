FROM docker.io/python:3.10

COPY ./ /src

WORKDIR /src

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# RUN pip install poetry
# RUN poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi

CMD [ "python", "worker.py" ]