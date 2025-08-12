# Bidding Analysis Application with Streamlit and Docker

This is a Streamlit application that allows users to analyze PDF bidding documents and chat with a language model about their content.

## Prerequisites

Make sure you have **Docker** installed on your system.

  - [Install Docker](https://docs.docker.com/get-docker/)

-----

## How to Run the Application

Follow these steps to build the Docker image and run the container:

### 1\. Build the Docker Image

Open a terminal in the project directory and run the following command:

```sh
docker build -t bidding-app .
```

  * `docker build`: The command to build a Docker image.
  * `-t bidding-app`: Assigns a name (`bidding-app`) to the image.
  * `.`: Indicates that the `Dockerfile` and the build context are in the current directory.

This process may take a few minutes the first time, as Docker will download the base Python image and install the dependencies.

### 2\. Run the Container

Once the image is built, you can run the application with the following command:

```sh
docker run -p 8501:8501 bidding-app
```

  * `docker run`: The command to run a container from an image.
  * `-p 8501:8501`: Maps port **8501** on your local machine to port **8501** on the container. This allows you to access the application in your browser.
  * `bidding-app`: The name of the image you built in the previous step.

### 3\. Access the Application

After running the `docker run` command, the application will be available in your browser. Open the following URL:

[http://localhost:8501](https://www.google.com/search?q=http://localhost:8501)

### 4\. Additional Configuration

The application requires the `API_BASE_URL` environment variable. You can provide it when running the container using the `-e` flag:

```sh
docker run -p 8501:8501 -e "API_BASE_URL=http://your-backend-api.com" bidding-app
```

Replace `http://your-backend-api.com` with the URL of your backend API.