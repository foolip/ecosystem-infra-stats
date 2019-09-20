# Ecosystem Infra Stats

This is a collection of scripts to compute stats for
[ecosystem infra](https://bit.ly/ecosystem-infra), backing
[some graphs](https://foolip.github.io/ecosystem-infra-stats/).

This is intended to replace the
[old stats spreadsheet](https://bit.ly/ecosystem-infra-stats).

## Setup

An up-to-date checkout of [wpt](https://github.com/web-platform-tests/wpt) is
needed in `$HOME/web-platform-tests/wpt`.

The build script needs Python 2 and Virtualenv:
```bash
sudo apt install python2 virtualenv
```

## Build & deploy

To build and serve locally:
```bash
./build.sh && ./serve.sh
```

This will serve the tool at http://localhost:8000/ecosystem-infra-stats/

To build and deploy to the gh-pages branch:
```bash
./build.sh && ./deploy.sh
```
