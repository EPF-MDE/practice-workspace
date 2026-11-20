#!/bin/sh
set -e

npm install
npm --prefix frontend install
(cd backend && uv sync)
