# Use a lightweight base image with Flutter pre-installed or install it
FROM ghcr.io/cirruslabs/flutter:stable

# Set working directory
WORKDIR /app

# Copy the dependency files first to cache dependencies
COPY pubspec.yaml pubspec.lock ./

# Get dependencies
RUN flutter pub get

# Copy the rest of the application code
COPY . .

# Expose the port
EXPOSE 3000

# Enable web support (just in case it's disabled, though usually enabled by default in recent versions)
RUN flutter config --enable-web

# Run the application
# We use web-server device for headless execution in container
CMD ["flutter", "run", "-d", "web-server", "--web-port", "3000", "--web-hostname", "0.0.0.0"]
