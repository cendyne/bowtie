FROM python:3.9-slim-buster

WORKDIR /app
ADD requirements.txt /app/
RUN pip3 install -r requirements.txt
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends imagemagick sqlite3 ffmpeg

ADD start.sh bot.py bowtiedb.py supervisord.conf /app/

CMD ["bash", "start.sh"]
