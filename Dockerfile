FROM python:bullseye

EXPOSE 8000
WORKDIR /amm
COPY requirements.txt /amm/
RUN pip3 install -r requirements.txt
RUN python 3rd/mexc-sdk-1.0.0/setup.py install
COPY . /amm/
