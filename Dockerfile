FROM rust:1.89-bookworm AS build
ARG TPCHGEN_VERSION=3.0.0
RUN cargo install tpchgen-cli --version "${TPCHGEN_VERSION}" --locked

FROM debian:bookworm-slim
COPY --from=build /usr/local/cargo/bin/tpchgen-cli /usr/local/bin/tpchgen-cli
WORKDIR /out
VOLUME /out
ENTRYPOINT ["tpchgen-cli"]
