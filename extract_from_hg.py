#!/usr/bin/python

##
# This script is designed to import Loop standalone content from
# mozilla-central, to the git repo, with necessary translations of
# file locations, and some in-file corrections.
#
# It is typically expected to be run from a cron job.
#
# It expects to be run in the root directory of
# https://github.com/mozilla/loop-client
# and expects http://hg.mozilla.org/mozilla-central/ to be in
# "../mozilla-central"
#
# It also assumes the "origin" remote is correctly set on the repository
##

import argparse
import sys
import os
from datetime import datetime
import subprocess
import dateutil
import dateutil.tz
import re
from mercurial import hg, ui, commands
# We use gitpython for the repository branch. I was hoping to use it for
# more, but unfortunately gitpython doesn't seem to want
# to set dates on commits, so we revert to calling git directly for that.
# Also push and pull just didn't seem to work - the documentation is really
# minimal, which doesn't help.
from git import Repo

CHANGELOG_FILE = "CHANGELOG"
LATEST_REV_FILE = "last_m_c_import_rev.txt"
DEFAULT_SOURCE_REPO = "http://hg.mozilla.org/mozilla-central/"
DEFAULT_SOURCE_CLONE = "../mozilla-central"
DEFAULT_SOURCE_BRANCH = "default"


# Is this interesting to Loop?
def interestingFilename(filename):
    return (filename.startswith("browser/extensions/loop/standalone") or
            filename.startswith("browser/extensions/loop/content/shared") or
            filename.startswith("browser/extensions/loop/test/standalone") or
            filename.startswith("browser/extensions/loop/test/shared"))


def isIndexFile(filename):
    return filename == "browser/extensions/loop/standalone/content/index.html"


# This is how we map files from mozilla-central to loop-client repo
def updatePathsFor(filename):
    filename = filename.replace("browser/extensions/loop/standalone/", "")
    filename = filename.replace("browser/extensions/loop/content/shared/",
                                "content/shared/")
    filename = filename.replace("browser/extensions/loop/test/standalone/",
                                "test/standalone/")
    filename = filename.replace("browser/extensions/loop/test/shared/",
                                "test/shared/")
    return filename


def preserveLocaleData(filename, fileData):
    """
    Preserves locale data for an index file.

    Keyword arguments:
    filename -- the filename of the original file
    fileData -- the new file data being written
    """
    oldFile = open(filename, "r")
    oldFileData = oldFile.read()
    oldFile.close()

    localeList = re.search(r"""
      <meta                          # Match tag name
        \s*                          # Any number of spaces
        name=(["'])locales\1.*?      # Match name="locales" (either kind of quote)
        \s*                          # Any number of spaces
        content=(["'])               # Match content attribute
          (.*?)                      # The locale information we want
          \2.*?                      # End quote of content attribute
        \s*                          # Any number of spaces
       />
    """, oldFileData, re.VERBOSE).group(3)

    # This will overwrite any other attributes, but we only expect these
    # so that should be fine.
    newFileData = re.sub(r"""
      <meta                        # Match tag name
        \s*                        # Any number of spaces
        name=(["'])locales\1.*?    # Match name="locales" (either kind of quote)
        \s*                        # Any number of spaces
        content=(["']).*?\2.*?     # Match content="<anything>" attribute
        \s*                        # Any number of spaces
       />
    """,
        '<meta name="locales" content="' + "".join(localeList) + '" />',
        fileData, 1, re.MULTILINE | re.DOTALL | re.VERBOSE)

    return newFileData


def testFileNeedsUpdatedPaths(filename):
    return (filename == "test/standalone/index.html" or
            filename == "test/shared/index.html")


def updatePathsInTestFile(filename, fileData):
    print "Translating %s" % filename
    return fileData.replace('src="../../standalone/', 'src="../../')

def stripPackageJson(fileData):
    # This line we don't want - we don't use eslint in loop-client currently
    # and we don't want to move the source across.
    return fileData.replace('"eslint-plugin-mozilla": "../../../../testing/eslint-plugin-mozilla",', '')

def writeFile(filename, fileData):
    """
    Write a file out to disk

    Keyword arguments:
    filename -- the filename to write
    fileData -- text file content
    """
    directory = os.path.dirname(filename)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)

    outFile = open(filename, "w")
    if testFileNeedsUpdatedPaths(filename):
        outFile.write(updatePathsInTestFile(filename, fileData))
    elif filename == "package.json":
        outFile.write(stripPackageJson(fileData))
    else:
        outFile.write(fileData)
    outFile.close()


def deleteFile(filename):
    os.remove(filename)


def runCommand(cmd):
    p = subprocess.Popen(cmd)
    result = p.wait()
    if result != 0:
        print >> sys.stderr, "FAIL: Unable to run %s, exit code: %d" % (cmd, result)
        sys.exit(result)


def gitAdd(filename):
    runCommand(['git', 'add', filename])


def gitRemove(filename):
    runCommand(['git', 'rm', filename])


# Deals with writing all parts of a cset to disk, updating the git index
# as we go.
def writeCset(cset):
    print "%s %s" % (cset.hex(), cset.description())

    for filename in cset.files():
        # Write the files
        if interestingFilename(filename):
            newFilename = updatePathsFor(filename)
            try:
                fileContext = cset[filename]
            except:
                # print "Deleting file %s" % (filename)
                deleteFile(newFilename)
                gitRemove(newFilename)
            else:
                fileData = fileContext.data()

                # For the index file, we preserve the locale data in the file.
                if isIndexFile(filename):
                    fileData = preserveLocaleData(newFilename, fileData)

                # print "Writing %s to %s" % (filename, newFilename)
                writeFile(newFilename, fileData)
                gitAdd(newFilename)


# Actually commits the cset
def commitCset(cset):
    commitMsg = "%s\nmozilla-central hg revision: %s" % (cset.description(),
                                                         cset.hex())
    csetDate = datetime.fromtimestamp(cset.date()[0],
                                      dateutil.tz.tzoffset(None,
                                                           -cset.date()[1]))
    runCommand(['git', 'commit', '-m', commitMsg, '--author=' + cset.user(),
                '--date=' + str(csetDate)])

def formatCommitMessageLine(line):
    # Now do translations on the line.

    # First, strip off any review flags from the end of line.
    line = re.sub(r"""
     \ *         # Match any number of spaces
     \[*         # Match none or more of `[`, don't worry about `]` - some commit messages do `[r=smith]`
     rs*         # Match r or rs
     \=.*        # Match = and the rest of the line.
    """, "", line, 0, re.VERBOSE)

    # Now change any ': ' to dashes - some people use "Bug 123456: ..."
    line = re.sub(r": ", " - ", line)

    # Next change any '123456-' to add a space either side of the dash.
    # Some people do 'Bug 123456-...'.
    line = re.sub(r"\([0-9]]\)-", r"\1 - ", line)

    # Now replace any commas at the end of the line with dots.
    line = re.sub(r",$", ".", line)

    # Finally insert '- ' at start of line for changelog formatting.
    return "- " + line


def insertGitChanges(gitRepo, headGitCommit, outFile):
    proc = subprocess.Popen(
        ['git', 'log',
         headGitCommit + ".." + gitRepo.head.object.hexsha,
         "--decorate=no",
         "--reverse",
         "--format=format:%s"],
        stdout=subprocess.PIPE)

    while True:
        line = proc.stdout.readline()
        if line == '':
            break

        # We shouldn't ever hit this, but just in case...
        if line.startswith('update latest merged cset file and CHANGELOG'):
            continue

        outFile.write(formatCommitMessageLine(line) + "\n")


def writeChangeLog(gitRepo, headGitCommit):
    inFile = open(CHANGELOG_FILE, "r")
    oldLines = inFile.readlines()
    inFile.close()

    outFile = open(CHANGELOG_FILE, "w")
    foundTBD = False
    foundFirstDashes = False
    outBuffer = []

    continuationIndex = 0

    # Find where to insert the new lines. We hunt down to the first TBD followed
    # by "---" and then look for the next one. Note that 'i' gets used in the for
    # statement lower down to finish writing the file.
    for i in xrange(len(oldLines)):
        line = oldLines[i]
        strippedLine = line.rstrip('\n')

        if foundTBD and foundFirstDashes:
            if line.startswith("---"):
                # Now we've found the dashes, print the buffer and adjust the index
                # so that we're ready for later.
                for bufferLine in outBuffer[:-2]:
                    outFile.write(bufferLine)

                continuationIndex = i - 2
                break

            outBuffer.append(line)

        else:
            if strippedLine == "TBD":
                foundTBD = True
            elif foundTBD and line.startswith("---"):
                foundFirstDashes = True

            outFile.write(line)

    # Now get the git log entries and add them to the file. If this fails, we
    # still finish writing the CHANGELOG, so as to not leave the repo in a totally
    # bad state.
    try:
        insertGitChanges(gitRepo, headGitCommit, outFile)
    except Exception, e:
        print >> sys.stderr, "Running insertGitChanges failed: ", e

    # Finally output the rest of the changelog.
    for i in xrange(continuationIndex, len(oldLines)):
        outFile.write(oldLines[i])

    outFile.close()


# Outputs to the lastest revision file
def writeLatestRevAndChangeLog(gitRepo, headGitCommit, cset):
    writeChangeLog(gitRepo, headGitCommit)
    gitAdd(CHANGELOG_FILE)

    outFile = open(LATEST_REV_FILE, "w")
    outFile.write(cset.hex() + "\n")
    outFile.close()

    gitAdd(LATEST_REV_FILE)
    runCommand(['git', 'commit', '-m', 'update latest merged cset file and CHANGELOG'])


def pullHg(hgRepo, hgUI, sourceURL, sourceBranch):
    # And update it
    if commands.incoming(hgUI, hgRepo, source=sourceURL, bundle=None,
                         force=None) == 0:
        commands.pull(hgUI, hgRepo, source=sourceURL)
        commands.update(hgUI, hgRepo, rev=sourceBranch)


def pullGit(branch):
    runCommand(['git', 'pull', '-q', '--ff-only', 'origin', branch])


def pushGit(branch):
    runCommand(['git', 'push', '-q', 'origin', branch])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--push-result', dest='push_result',
                        action='store_true', default=False,
                        help='Push the result of the extraction')
    parser.add_argument('--source-repo', dest='source_repo',
                        action='store', default=DEFAULT_SOURCE_REPO,
                        help='Hg source repository (default: %s)' % DEFAULT_SOURCE_REPO)
    parser.add_argument('--source-clone', dest='source_clone',
                        action='store', default=DEFAULT_SOURCE_CLONE,
                        help='Hg clone repository location (default: %s)' % DEFAULT_SOURCE_CLONE)
    parser.add_argument('--source-branch', dest='source_branch',
                        action='store', default=DEFAULT_SOURCE_BRANCH,
                        help='Hg default source branch (default: %s)' % DEFAULT_SOURCE_BRANCH)
    parser.add_argument('--skip-pull-git', dest='pull_git',
                        action='store_false', default=True,
                        help='Skips pulling the git repo. Useful for local testing or if on branches')
    parser.add_argument('--skip-pull-hg', dest='pull_hg',
                        action='store_false', default=True,
                        help='Skips pulling the hg repo. Useful for local testing.')

    args = parser.parse_args()

    # First of all, check we're up to date for the git repo.
    gitRepo = Repo(".")
    assert gitRepo.bare is False
    assert gitRepo.is_dirty() is False

    if args.pull_git:
        pullGit(gitRepo.active_branch.name)

    headGitCommit = gitRepo.head.object.hexsha

    # Find out the last revision we checked against
    lastestRevFile = open(LATEST_REV_FILE, "r")
    firstRevText = lastestRevFile.read().strip()
    lastestRevFile.close()

    # Open the Mercurial repo...
    hgUI = ui.ui()
    hgRepo = hg.repository(hgUI, args.source_clone)

    if args.pull_hg:
        pullHg(hgRepo, hgUI, args.source_repo, args.source_branch)

    committedFiles = False
    firstRev = hgRepo[firstRevText].rev() + 1

    print "Starting at %s" % (hgRepo[firstRev].hex())

    # Now work through any new changesets
    for i in xrange(firstRev, len(hgRepo)):
        cset = hgRepo[i]

        # Use the very last cset, not the one that affects loop,
        # to avoid attempting to port the same cset all the time
        lastCset = cset

        if len(cset.parents()) > 1:
            continue

        affectsLoop = False
        # If one of the files is interesting to loop, then we need to
        # do the whole changeset
        for filename in cset.files():
            if interestingFilename(filename):
                print filename
                affectsLoop = True
                break

        if affectsLoop:
            # Create a new index for the repo (indexes get translated
            # into commits)
            # Write the cset, then commit it.
            writeCset(cset)
            commitCset(cset)
            committedFiles = True

    # Only bother committing and pushing if we've updated the files.
    if committedFiles:
        writeLatestRevAndChangeLog(gitRepo, headGitCommit, lastCset)

        if args.push_result:
            pushGit(gitRepo.active_branch.name)

if __name__ == "__main__":
    main()
