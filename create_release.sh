#!/bin/bash -e

if (( $# != 1 )); then
    echo "Please specify the tag"
    exit 1;
fi

LOOP_CLIENT_DIR=$(basename $(pwd))
TAG=$1

echo "Tagging..."
git tag -a $1 -m "Release $1"

echo "Make version..."
make version

echo "Creating tar package..."
cd ..
tar zcvf loop-client-$1.tar.gz --exclude=.git --exclude=test --exclude=node_modules $LOOP_CLIENT_DIR
zip -r loop-client-$1.zip --exclude=*.git* --exclude=*test* --exclude=*node_modules* $LOOP_CLIENT_DIR
cd $LOOP_CLIENT_DIR

echo "Pushing new tags..."
git push --tags

