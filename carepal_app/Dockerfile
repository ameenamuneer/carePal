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

# To build Android APK, comment the line above and uncomment the line below
# After the container finishes running, the APK will be available at carepal_app/build/app/outputs/flutter-apk/app-release.apk
# CMD ["flutter", "build", "apk", "-v"]
# CMD ["flutter", "run"]
