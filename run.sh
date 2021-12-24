#!/bin/bash

if [[ -f ".env" ]]; then
    echo "Adding .env"
    export $(egrep -v '^#' .env | sed -e 's/#.*$//;/^$/d' | xargs)
fi

mkdir -p "$DOWNLOADS_PATH"
mkdir -p "$WEB_PATH"

supervisord -n