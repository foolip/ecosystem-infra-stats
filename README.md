# Ecosystem Infra Stats

This is a collection of scripts to compute stats for
[ecosystem infra](https://bit.ly/ecosystem-infra), backing
[some graphs](https://foolip.github.io/ecosystem-infra-stats/).

This is intended to replace the
[old stats spreadsheet](https://bit.ly/ecosystem-infra-stats).

## Setup

Up-to-date checkouts of
[Chromium](https://www.chromium.org/developers/how-tos/get-the-code)
and [web-platform-tests](https://github.com/w3c/web-platform-tests)
are needed in `$HOME/chromium/src` and `$HOME/web-platform-tests`.

The build script needs Python 2 and Virtualenv:
```bash
sudo apt install python2 virtualenv
```

Finally, [generate a new access token](https://github.com/settings/tokens/new)
and set `GH_TOKEN` in the environment to the value.

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