# PostgreSQL 18 with the EDB Postgres Analytics Accelerator (pgaa, which bundles Seafowl) and pgfs.
# Put the two .deb files in debs/ (see README.md). The Debian 12 package matches this base image.
FROM postgres:18.6-bookworm
# The base image has no CA bundle; without it pgfs cannot reach S3 over TLS.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY debs/*.deb /tmp/debs/
RUN apt-get update && apt-get install -y --no-install-recommends /tmp/debs/*.deb \
 && rm -rf /var/lib/apt/lists/* /tmp/debs
