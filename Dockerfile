FROM ubuntu:latest

RUN apt-get update
RUN apt-get install -y \
    wget \
    python3-pip

WORKDIR /opt

RUN pip install --upgrade pip

RUN pip3 install jupyterlab==3.4.8

EXPOSE 8888