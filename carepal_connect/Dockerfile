FROM ghcr.io/cirruslabs/flutter:stable

WORKDIR /app

# Copy dependency files first to cache the pub get layer
COPY pubspec.yaml pubspec.lock* ./

# Get dependencies
RUN flutter pub get

# Copy the rest of the source
COPY . .

EXPOSE 3001

RUN flutter config --enable-web

CMD ["flutter", "run", "-d", "web-server", "--web-port", "3001", "--web-hostname", "0.0.0.0"]
