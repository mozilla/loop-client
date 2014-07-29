#!/bin/bash -e
TMP=${TMP-/tmp}
LOOP_CLIENT=$(pwd)
GECKO_DEV=$(pwd)/../gecko-dev/
GECKO_BRANCH=master

# Update gecko-dev
cd $GECKO_DEV
echo " = UPDATING GECKO-DEV ="
pwd
git checkout master
git pull
GECKO_REV=$(git rev-parse HEAD)
TAR_GZ_NAME="loop-client_${GECKO_REV}.tar.gz"

# Update loop-client
cd $LOOP_CLIENT
echo -e "\n = UPDATING LOOP-CLIENT ="
pwd
git checkout master
git pull

echo -e "\n = UPGRADING LOOP-CLIENT from GECKO-DEV ="
# Clean current content
rm -fr content/ test/

# Update loop-client from gecko-dev
cp -fr ${GECKO_DEV}/browser/components/loop/standalone/* ${LOOP_CLIENT}
cp -fr ${GECKO_DEV}/browser/components/loop/content/shared/ ${LOOP_CLIENT}/content/shared/
mkdir -p ${LOOP_CLIENT}/test
cp -fr ${GECKO_DEV}/browser/components/loop/test/standalone ${LOOP_CLIENT}/test
cp -fr ${GECKO_DEV}/browser/components/loop/test/shared ${LOOP_CLIENT}/test

# Build snapshot
cd $LOOP_CLIENT/..
echo -e "\n = BUILDING ${TMP}/${TAR_GZ_NAME} ="
tar zcvf "${TMP}/${TAR_GZ_NAME}" --exclude=.git --exclude=test --exclude=node_modules $(basename $LOOP_CLIENT)

cd $LOOP_CLIENT
echo -e "\n = COMMITING new snapshot ="
pwd
git add -u .; git add .; git commit -m "Update to gecko-dev REV ${GECKO_REV}."
echo -e "\n Snapshot in: ${TMP}/${TAR_GZ_NAME}"
echo -e "\n Don't forget to push you changes to loop-client if you are ok with them."
