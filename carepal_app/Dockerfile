# Stage 1: Build
FROM debian:latest AS build-env

RUN apt-get update
RUN apt-get install -y curl git wget unzip libgconf-2-4 gdb libstdc++6 libglu1-mesa fonts-droid-fallback lib32stdc++6 python3
RUN apt-get clean

# Clone Flutter
RUN git clone https://github.com/flutter/flutter.git /usr/local/flutter

# Set flutter path
ENV PATH="/usr/local/flutter/bin:/usr/local/flutter/bin/cache/dart-sdk/bin:${PATH}"

# Run flutter doctor
RUN flutter doctor

# Copy files
RUN mkdir /app
COPY . /app
WORKDIR /app

# Build web
RUN flutter config --enable-web
RUN flutter pub get
RUN flutter build web

# Stage 2: Serve
FROM nginx:1.21.1-alpine
COPY --from=build-env /app/build/web /usr/share/nginx/html
