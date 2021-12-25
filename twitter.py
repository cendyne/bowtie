import os
import json
import time
import logging
import datetime
import urllib.request
from typing import List, Optional, Text
import tweepy
import tweepy.models
import bowtiedb

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

downloads_path = os.environ["DOWNLOADS_PATH"]

auth = tweepy.OAuthHandler(os.environ["TWITTER_KEY"], os.environ["TWITTER_SECRET"])
auth.set_access_token(os.environ["TWITTER_ACCESS_TOKEN"], os.environ["TWITTER_ACCESS_TOKEN_SECRET"])
api = tweepy.API(auth)

# print("key %s", os.environ["TWITTER_KEY"])
# print("secret %s", os.environ["TWITTER_SECRET"])
# print("access %s", os.environ["TWITTER_ACCESS_TOKEN"])
# print("access secret %s", os.environ["TWITTER_ACCESS_TOKEN_SECRET"])

# test authentication


@bowtiedb.with_connection
def handleTimeline(timeline: List[tweepy.models.Status]) -> None:
    for status in timeline:
        if hasattr(status, 'retweeted_status'):
            status = status.retweeted_status
        if bowtiedb.has_tweet(status.id):
            continue
        # print("status %s", status)
        created_at: datetime.datetime = status.created_at
        created_at_unixtime = int(time.mktime(created_at.timetuple()))
        text:Text = status.full_text
        if status.display_text_range:
            text = text[status.display_text_range[0]:status.display_text_range[1]]
        author:tweepy.models.User = status.author
        author_name = author.screen_name
        profile_image:Optional[Text] = None
        if hasattr(author, 'profile_image_url'):
            profile_image = author.profile_image_url
            profile_image = profile_image.replace("_normal", "")
        photo_url = None
        if hasattr(status, 'extended_entities'):
            extended_entities:dict = status.extended_entities
            if extended_entities and extended_entities["media"] and len(extended_entities["media"]) > 0 and extended_entities["media"][0]["media_url"]:
                photo_url = extended_entities["media"][0]["media_url"]
        # TODO save tweet json
        download_profile_image = None
        if profile_image:
            download_profile_image = profile_image.replace("http://pbs.twimg.com/", "").replace("/", "_")
            if not os.path.exists(downloads_path + "/" + download_profile_image):
                with urllib.request.urlopen(profile_image) as f:
                    with open(downloads_path + "/" + download_profile_image, 'wb') as fh:
                        fh.write(f.read())
                        logging.info("Wrote %s", download_profile_image)
        download_photo_url = None
        if photo_url:
            download_photo_url = photo_url.replace("http://pbs.twimg.com/", "").replace("/", "_")
            if not os.path.exists(downloads_path + "/" + download_photo_url):
                with urllib.request.urlopen(photo_url) as f:
                    with open(downloads_path + "/" + download_photo_url, 'wb') as fh:
                        fh.write(f.read())
                        logging.info("Wrote %s", download_photo_url)
        bowtiedb.save_tweet(status.id, json.dumps(status._json))
        bowtiedb.add_entry(bowtiedb.Entry(created_at_unixtime, text, download_photo_url, [], author_name, download_profile_image))
        print(author_name, download_profile_image, created_at_unixtime, text, download_photo_url)
def main() -> None:
    bowtiedb.init()
    try:
        user: tweepy.User = api.verify_credentials()
        print("Authentication OK")
    except Exception as e:
        print("Error during authentication %s", e)
        time.sleep(300)
        exit(1)
    # auth.set_access_token(access_token, access_token_secret)

    # print("%s",api.home_timeline())
    print("User id %s", user.id)

    while True:
        try:
            timeline: List[tweepy.models.Status] = api.user_timeline(user_id=user.id, include_rts=True, tweet_mode='extended', count=10)
            handleTimeline(timeline)
        except Exception as e:
            logging.error("An error!", e)
        time.sleep(60)

if __name__ == '__main__':
    main()
