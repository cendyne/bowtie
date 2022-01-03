FROM python:3.9-slim-buster

WORKDIR /app
ADD requirements.txt /app/
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends imagemagick \
    sqlite3 ffmpeg build-essential
RUN pip3 install -r requirements.txt


ADD run.sh bot.py twitter.py gen.py bowtiedb.py supervisord.conf /app/
ADD static /app/static/

CMD ["bash", "run.sh"]
